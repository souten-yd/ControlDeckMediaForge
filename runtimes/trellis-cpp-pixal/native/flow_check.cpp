// Trusted local synthetic fixtures only. GPU caller must hold a real Host lease.
#include "flow_runner.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace trellis { extern bool g_no_fa; }
namespace pixal = mediaforge::pixal;
int main(int argc, char** argv) {
    try {
        if (argc < 4) throw std::invalid_argument("usage: pixal-flow-check <fixture> <gguf> cpu|vulkan [--device N]");
        const std::string directory = argv[1], checkpoint = argv[2], kind = argv[3];
        int device = -1, cancel_after = -1;
        bool omit_proj=false, omit_concat=false, nan=false, short_output=false, analytic=false;
        for (int i=4; i<argc; ++i) {
            const std::string flag = argv[i];
            if (flag == "--device" && i+1<argc) device = std::stoi(argv[++i]);
            else if (flag == "--cancel-after" && i+1<argc) cancel_after = std::stoi(argv[++i]);
            else if (flag == "--omit-proj") omit_proj = true;
            else if (flag == "--omit-concat") omit_concat = true;
            else if (flag == "--nan-velocity") nan = true;
            else if (flag == "--short-output") short_output = true;
            else if (flag == "--analytic") analytic = true;
            else throw std::invalid_argument("unknown flow check argument");
        }
        if ((kind != "cpu" && kind != "vulkan") || (kind == "vulkan") != (device >= 0))
            throw std::invalid_argument("select CPU or an explicit Vulkan device index");
        auto spec = pixal::inspect_flow_checkpoint(checkpoint);
        if (spec.params.n_blocks > 4 || spec.params.d_model > 256)
            throw std::invalid_argument("flow check accepts small synthetic checkpoints only");
        std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(
            kind == "cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(device), ggml_backend_free);
        if (!backend) throw std::runtime_error("requested backend unavailable");
        if (kind == "cpu") ggml_backend_cpu_set_n_threads(backend.get(), 2);
        const auto backend_name = std::string(ggml_backend_name(backend.get()));
        size_t allocation = 0;
        int calls = 0;
        std::vector<std::array<int,3>> coords;
        auto load = [&](const std::string& name) {
            auto value = npy::load(directory + "/" + name + ".npy");
            if (value.numel() > 4000000) throw std::invalid_argument("fixture too large");
            return value;
        };
        auto coordinate_array = load("coordinates");
        if (coordinate_array.shape.size()!=2 || coordinate_array.shape[1]!=3 || coordinate_array.shape[0]>4096)
            throw std::invalid_argument("invalid synthetic coordinates");
        for (size_t i=0; i<coordinate_array.data.size(); i+=3) {
            std::array<int,3> c;
            for (int j=0; j<3; ++j) {
                float value = coordinate_array.data[i+j];
                if (!std::isfinite(value) || value<0 || value>4095 || std::floor(value)!=value)
                    throw std::invalid_argument("invalid coordinate fixture");
                c[j] = int(value);
            }
            coords.push_back(c);
        }
        auto global = load("global");
        if (global.shape.size()!=2 || global.shape[1]!=spec.params.d_cond)
            throw std::invalid_argument("invalid synthetic global condition");
        pixal::FlowCondition positive{global.data, load("projected").data};
        pixal::FlowCondition negative{load("negative_global").data, load("negative_projected").data};
        if (omit_proj) positive.projected.clear();
        const auto noise = load("noise").data;
        std::vector<float> concat;
        if (spec.stage == "texture" && !omit_concat) concat = load("concat").data;
        pixal::FlowSamplerParams params;
        std::ifstream config(directory + "/sampler.txt");
        config >> params.steps >> params.rescale_t >> params.sigma_min >> params.guidance_strength
               >> params.guidance_rescale >> params.interval_start >> params.interval_end;
        if (!config) throw std::invalid_argument("invalid sampler fixture");
        std::vector<pixal::FlowStep> trace;
        std::vector<float> samples;
        std::vector<std::array<int,2>> progress;
        std::vector<float> forward_log;
        {
            pixal::FlowModel model(checkpoint, backend.get());
            trellis::g_no_fa = true; // F32 oracle; FlashAttention is a separate gate.
            pixal::FlowRunner runner(model, coords, int(global.shape[0]), true);
            allocation = runner.graph_bytes();
            auto forward = [&](const std::vector<float>& x, float t, const pixal::FlowCondition& condition) {
                ++calls;
                forward_log.push_back(t);
                forward_log.push_back(&condition == &positive ? 1.f : 0.f);
                auto out = analytic ? x : runner.forward(x, t, condition, concat);
                if (analytic) {
                    // Adversarial scale canary: exact CFG residual near 1e-2
                    // gives a reference rescale ratio far above TRELLIS's clamp.
                    for (size_t i=0; i<out.size(); ++i)
                        out[i] = (&condition == &positive ? -1.f : -2.99f)*x[i];
                }
                if (nan) out[0] = std::numeric_limits<float>::quiet_NaN();
                if (short_output) out.pop_back();
                return out;
            };
            auto cancelled = [&] { return cancel_after >= 0 && calls >= cancel_after; };
            auto observe = [&](int done, int total) { progress.push_back({done,total}); };
            samples = pixal::sample_flow(forward, noise, positive, negative, params, spec.stage != "ss",
                                         spec.params.out_ch, &trace, cancelled, observe);
            const auto repeat = pixal::sample_flow(forward, noise, positive, negative, params, spec.stage != "ss",
                                                    spec.params.out_ch);
            if (samples != repeat) throw std::runtime_error("reused graph is not deterministic");
        }
        // Destruction of model/runner must leave their borrowed backend alive.
        if (std::string(ggml_backend_name(backend.get())) != backend_name)
            throw std::runtime_error("borrowed backend was changed");
        for (size_t i=0; i<trace.size(); ++i) {
            const auto prefix = directory + "/actual_step" + std::to_string(i);
            const std::vector<int64_t> shape{(int64_t)coords.size(), spec.params.out_ch};
            npy::save(prefix + "_velocity.npy", trace[i].velocity.data(), shape);
            npy::save(prefix + "_clean.npy", trace[i].predicted_clean.data(), shape);
            npy::save(prefix + "_sample.npy", trace[i].sample.data(), shape);
        }
        npy::save(directory + "/actual_forward_log.npy", forward_log.data(), {(int64_t)forward_log.size()/2,2});
        std::ofstream report(directory + "/native_result.json");
        report << "{\"graph_bytes\":" << allocation << ",\"forwards_including_repeat\":" << calls
               << ",\"progress_events\":" << progress.size() << ",\"borrowed_backend_retained\":true}\n";
        std::cout << "backend=" << backend_name << " steps=" << trace.size() << " forwards=" << calls << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n'; return 1;
    }
}
