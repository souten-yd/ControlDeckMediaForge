// Bounded private operator probe. Genuine GPU admission belongs to the caller.
#include "bounded_npy.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <charconv>
#include <cstdlib>
#include <iostream>
#include <memory>

int main(int argc, char** argv) {
    try {
        if (argc != 5 && argc != 6)
            throw std::invalid_argument("usage: pixal-softmax-check INPUT OUTPUT cpu|vulkan DEVICE [SINK]");
        const std::string kind = argv[3], device_text = argv[4];
        int device = -2;
        const auto parsed = std::from_chars(device_text.data(), device_text.data()+device_text.size(), device);
        if (parsed.ec != std::errc{} || parsed.ptr != device_text.data()+device_text.size() ||
            (kind != "cpu" && kind != "vulkan") || (kind == "cpu" ? device != -1 : device < 0 || device > 31))
            throw std::invalid_argument("explicit backend/device required");
        const auto input = mediaforge::pixal::read_input_array(argv[1], 32*1024*1024);
        if (input.shape.size() != 2 || input.shape[0] > 1024 || input.shape[1] > 65536 ||
            std::filesystem::exists(argv[2]))
            throw std::invalid_argument("bounded matrix and fresh output required");
        std::vector<float> sink;
        if (argc == 6) sink = mediaforge::pixal::read_input_array(argv[5], 1).data;
        if (kind == "vulkan")
            for (const char* name : {"GGML_VK_DISABLE_F16", "GGML_VK_DISABLE_COOPMAT", "GGML_VK_DISABLE_COOPMAT2"})
                if (setenv(name, "1", 1) != 0) throw std::runtime_error("cannot enforce F32 policy");
        std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(
            kind == "cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(device), ggml_backend_free);
        if (!backend) throw std::runtime_error("requested backend unavailable");
        if (kind == "cpu") ggml_backend_cpu_set_n_threads(backend.get(), 2);
        std::unique_ptr<ggml_context, decltype(&ggml_free)> ctx(
            ggml_init({1024*1024, nullptr, true}), ggml_free);
        if (!ctx) throw std::runtime_error("cannot allocate metadata");
        auto* x = ggml_new_tensor_2d(ctx.get(), GGML_TYPE_F32, input.shape[1], input.shape[0]);
        auto* output = ggml_soft_max_ext(ctx.get(), x, nullptr, 1/std::sqrt(128.f), 0);
        ggml_tensor* sink_tensor = nullptr;
        if (!sink.empty()) {
            sink_tensor = ggml_new_tensor_1d(ctx.get(), GGML_TYPE_F32, 1);
            ggml_soft_max_add_sinks(output, sink_tensor);
        }
        auto* graph = ggml_new_graph(ctx.get());
        ggml_build_forward_expand(graph, output);
        std::unique_ptr<ggml_backend_buffer, decltype(&ggml_backend_buffer_free)> buffer(
            ggml_backend_alloc_ctx_tensors(ctx.get(), backend.get()), ggml_backend_buffer_free);
        if (!buffer) throw std::runtime_error("cannot allocate bounded softmax tensors");
        ggml_backend_tensor_set(x, input.data.data(), 0, input.data.size()*sizeof(float));
        if (sink_tensor) ggml_backend_tensor_set(sink_tensor, sink.data(), 0, sizeof(float));
        if (ggml_backend_graph_compute(backend.get(), graph) != GGML_STATUS_SUCCESS)
            throw std::runtime_error("softmax compute failed");
        std::vector<float> values(input.data.size());
        ggml_backend_tensor_get(output, values.data(), 0, values.size()*sizeof(float));
        npy::save(argv[2], values.data(), {int64_t(input.shape[0]), int64_t(input.shape[1])});
        size_t bad = 0;
        for (float v : values) if (!std::isfinite(v)) ++bad;
        std::cout << "{\"rows\":" << input.shape[0] << ",\"columns\":" << input.shape[1]
                  << ",\"nonfinite\":" << bad << "}\n";
        return bad ? 1 : 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
