// Allocation-only capacity probe. Does not run a forward pass or initialize GPU.
#include "flow_runner.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "trellis_args.h"
#include <charconv>
#include <chrono>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <sys/resource.h>

int main(int argc, char** argv) {
    try {
        if (argc != 3)
            throw std::invalid_argument("usage: pixal-flow-allocate-cpu CHECKPOINT TOKENS (0 = complete SS grid)");
        const std::string argument(argv[2]);
        int count = -1;
        auto parsed = std::from_chars(argument.data(), argument.data()+argument.size(), count);
        if (parsed.ec != std::errc{} || parsed.ptr != argument.data()+argument.size() || count < 0 || count > 65536)
            throw std::invalid_argument("token count must be an integer from 0 to 65536");
        auto spec = mediaforge::pixal::inspect_flow_checkpoint(argv[1]);
        if (spec.source_kind != "checkpoint" || (spec.stage == "ss") != (count == 0))
            throw std::invalid_argument("requires trained checkpoint and stage-appropriate token count");
        std::vector<std::array<int,3>> coords;
        if (count == 0) {
            if (spec.resolution > 32)
                throw std::invalid_argument("SS capacity probe is limited to a 32-cubed grid");
            coords = mediaforge::pixal::dense_coordinates(spec.resolution);
        } else {
            if (size_t(count) > size_t(spec.resolution)*spec.resolution*spec.resolution)
                throw std::invalid_argument("token count exceeds checkpoint grid");
            coords.reserve(count);
            for (int i = 0; i < count; ++i)
                coords.push_back({i/(spec.resolution*spec.resolution), (i/spec.resolution)%spec.resolution, i%spec.resolution});
        }
        // Require a caller-imposed address-space bound. This is an operator
        // diagnostic, not a way to reserve or measure production GPU capacity.
        rlimit limit{};
        if (getrlimit(RLIMIT_AS, &limit) != 0 || limit.rlim_cur == RLIM_INFINITY || limit.rlim_cur > 24ULL*1024*1024*1024)
            throw std::invalid_argument("run with an address-space limit of at most 24 GiB");
        const auto start = std::chrono::steady_clock::now();
        std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(ggml_backend_cpu_init(), ggml_backend_free);
        if (!backend) throw std::runtime_error("CPU backend unavailable");
        ggml_backend_cpu_set_n_threads(backend.get(), 2);
        trellis::g_no_fa = true; // Same arithmetic and attention path as worker_cli.
        mediaforge::pixal::FlowModel model(argv[1], backend.get());
        mediaforge::pixal::FlowRunner runner(model, coords, 5, true);
        rusage usage{};
        if (getrusage(RUSAGE_SELF, &usage) != 0) throw std::runtime_error("cannot read process RSS");
        std::cout << "{\"backend\":\"CPU\",\"stage\":\"" << spec.stage
                  << "\",\"tokens\":" << coords.size() << ",\"global_tokens\":5,\"blocks\":" << spec.params.n_blocks
                  << ",\"width\":" << spec.params.d_model
                  << ",\"weights_buffer_bytes\":" << ggml_backend_buffer_get_size(model.weights().buffer)
                  << ",\"graph_buffer_bytes\":" << runner.graph_bytes()
                  << ",\"process_peak_rss_bytes\":" << uint64_t(usage.ru_maxrss)*1024
                  << ",\"address_space_limit_bytes\":" << limit.rlim_cur
                  << ",\"elapsed_sec\":" << std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()
                  << ",\"forward_calls\":0,\"graph_pages_touched\":false,\"vram_measured\":false}\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
