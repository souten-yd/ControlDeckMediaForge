// Numerical test driver for synthetic, small Pixal3D/TRELLIS DiT fixtures.
#include "dit.h"
#include "projection.h"
#include "trellis_model.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <cctype>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>

namespace trellis { extern bool g_no_fa; }

int main(int argc, char** argv) {
    try {
        if (argc < 3) throw std::invalid_argument("usage: pixal-dit-check <fixture-dir> cpu|vulkan [--device N] [--omit-proj|--short-proj]");
        const std::string dir = argv[1], kind = argv[2];
        int device_index = -1;
        bool omit_projection = false, short_projection = false, legacy_gelu = false, from_features = false;
        for (int i = 3; i < argc; ++i) {
            const std::string flag = argv[i];
            if (flag == "--device" && i+1 < argc) device_index = std::stoi(argv[++i]);
            else if (flag == "--omit-proj") omit_projection = true;
            else if (flag == "--short-proj") short_projection = true;
            else if (flag == "--legacy-gelu") legacy_gelu = true;
            else if (flag == "--from-features") from_features = true;
            else throw std::invalid_argument("unknown test argument");
        }
        if ((kind != "cpu" && kind != "vulkan") || ((kind == "vulkan") != (device_index >= 0)))
            throw std::invalid_argument("select CPU or Vulkan with an explicit nonnegative device index");
        std::ifstream config(dir + "/params.txt");
        trellis::DiTParams p;
        int projected_channels = 0;
        config >> p.n_blocks >> p.n_heads >> p.head_dim >> p.d_model >> p.d_mlp
               >> p.d_cond >> projected_channels >> p.in_ch >> p.out_ch;
#ifdef MEDIAFORGE_UNPATCHED_DIT
        if (projected_channels != 0 || !legacy_gelu)
            throw std::invalid_argument("unmodified baseline supports only legacy TRELLIS conditioning/GELU");
#else
        p.proj_in_channels = projected_channels;
        p.exact_gelu = !legacy_gelu;
#endif
        if (!config || p.n_blocks < 1 || p.n_blocks > 4 || p.d_model < 1 || p.d_model > 256 ||
            p.n_heads < 1 || p.n_heads > 16 || p.head_dim < 8 || p.head_dim > 64 ||
            p.d_model != p.n_heads * p.head_dim || p.d_cond < 1 || p.d_cond > 256 ||
            projected_channels < 0 || projected_channels > 512 || p.in_ch < 1 || p.in_ch > 64 ||
            p.out_ch < 1 || p.out_ch > 64 || p.d_mlp < 1 || p.d_mlp > 1024)
            throw std::invalid_argument("invalid synthetic test dimensions");
        if (from_features && (projected_channels == 0 || omit_projection || short_projection))
            throw std::invalid_argument("combined projection test requires a complete projected condition");
        std::unique_ptr<ggml_context, decltype(&ggml_free)> ctx(
            ggml_init({ggml_tensor_overhead()*8192 + ggml_graph_overhead_custom(8192, false), nullptr, true}), ggml_free);
        if (!ctx) throw std::runtime_error("cannot allocate DiT test context");
        std::map<ggml_tensor*, std::vector<float>> data;
        auto load = [&](const std::string& name) {
            auto array = npy::load(dir + "/" + name + ".npy");
            if (array.shape.empty() || array.shape.size() > 4 || array.numel() > 4000000)
                throw std::invalid_argument("invalid test tensor");
            std::vector<int64_t> dimensions(array.shape.rbegin(), array.shape.rend());
            auto* tensor = ggml_new_tensor(ctx.get(), GGML_TYPE_F32, dimensions.size(), dimensions.data());
            ggml_set_name(tensor, name.c_str());
            ggml_set_input(tensor);
            data[tensor] = std::move(array.data);
            return tensor;
        };
        trellis::Model model;
        std::ifstream weights(dir + "/weights.txt");
        if (!weights) throw std::invalid_argument("missing synthetic weights list");
        std::string name;
        while (std::getline(weights, name)) {
            if (name.empty() || name.find("..") != std::string::npos ||
                name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._") != std::string::npos)
                throw std::invalid_argument("invalid synthetic weight name");
            model.tensors[name] = load("weights/" + name);
        }
        auto* h0 = load("input");
        auto* time = load("timestep");
        auto* cond = load("global");
        auto* cosine = load("cosine");
        auto* sine = load("sine");
        ggml_tensor* projected = nullptr;
        mediaforge::pixal::ProjectionPlan plan{};
        mediaforge::pixal::ProjectionInputs projection_inputs{};
        if (projected_channels > 0 && !omit_projection) {
            if (from_features) {
                auto* features = load("features"); // [H,W,C]
                const int width = features->ne[1], height = features->ne[2];
                auto camera = npy::load(dir + "/camera.npy");
                if (camera.shape != std::vector<int64_t>{5} || camera.data[3] != 512 || camera.data[4] != 2)
                    throw std::invalid_argument("unexpected combined test camera/grid dimensions");
                std::vector<std::array<int,3>> coords;
                for (int x = 0; x < 2; ++x) for (int y = 0; y < 2; ++y) for (int z = 0; z < 2; ++z)
                    coords.push_back({x,y,z});
                plan = mediaforge::pixal::project_front_view(coords, 2, width, height,
                    {camera.data[0], camera.data[1], camera.data[2], 512});
                auto* flat_features = ggml_reshape_2d(ctx.get(), features, features->ne[0], width*height);
                projection_inputs = mediaforge::pixal::build_projection(ctx.get(), flat_features, width, height, coords.size());
                projected = projection_inputs.result;
            } else {
                projected = load("projected");
            }
        }
        if (short_projection && projected)
            projected = ggml_view_2d(ctx.get(), projected, projected->ne[0], projected->ne[1]-1, projected->nb[1], 0);
        // Exact F32 attention isolates the projection/weight mapping from the
        // existing low-precision FlashAttention approximation. FA is a separate gate.
        trellis::g_no_fa = true;
        std::map<std::string, ggml_tensor*> intermediates;
        auto* output = trellis::build_dit_dense(ctx.get(), model, p, h0, time, cond, cosine, sine, &intermediates
#ifndef MEDIAFORGE_UNPATCHED_DIT
                                               , projected
#endif
                                               );
        auto* graph = ggml_new_graph_custom(ctx.get(), 8192, false);
        ggml_build_forward_expand(graph, output);
        for (auto& [label, tensor] : intermediates) {
            ggml_set_output(tensor);
            ggml_build_forward_expand(graph, tensor);
        }
        std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(
            kind == "cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(device_index), ggml_backend_free);
        if (!backend) throw std::runtime_error("requested backend unavailable");
        if (kind == "cpu") ggml_backend_cpu_set_n_threads(backend.get(), 2);
        for (int i = 0; i < ggml_graph_n_nodes(graph); ++i)
            if (!ggml_backend_dev_supports_op(ggml_backend_get_device(backend.get()), ggml_graph_node(graph, i)))
                throw std::runtime_error("requested backend does not support every DiT operation");
        std::unique_ptr<ggml_backend_buffer, decltype(&ggml_backend_buffer_free)> buffer(
            ggml_backend_alloc_ctx_tensors(ctx.get(), backend.get()), ggml_backend_buffer_free);
        if (!buffer) throw std::runtime_error("cannot allocate DiT tensors");
        for (auto& [tensor, values] : data)
            ggml_backend_tensor_set(tensor, values.data(), 0, values.size()*sizeof(float));
        if (from_features) mediaforge::pixal::upload_projection(projection_inputs, plan);
        if (ggml_backend_graph_compute(backend.get(), graph) != GGML_STATUS_SUCCESS)
            throw std::runtime_error("DiT compute failed");
        for (auto& [label, tensor] : intermediates) {
            std::vector<float> values(ggml_nelements(tensor));
            ggml_backend_tensor_get(tensor, values.data(), 0, values.size()*sizeof(float));
            npy::save(dir + "/actual_" + label + ".npy", values.data(), {tensor->ne[1], tensor->ne[0]});
        }
        std::cout << "backend=" << ggml_backend_name(backend.get()) << " projected_channels=" << projected_channels << '\n';
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }
}
