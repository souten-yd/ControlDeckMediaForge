// Numerical test driver; reads only locally generated NPY fixtures, no models.
#include "projection.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <cmath>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        if (argc != 3 && argc != 4)
            throw std::invalid_argument("usage: pixal-projection-check <fixture-dir> cpu|vulkan [device-index]");
        const std::string dir = argv[1], kind = argv[2];
        if (kind != "cpu" && kind != "vulkan") throw std::invalid_argument("unknown backend");
        if ((kind == "vulkan") != (argc == 4)) throw std::invalid_argument("Vulkan requires explicit device index");
        auto fmap = npy::load(dir + "/features.npy"); // [H,W,C]
        auto coords = npy::load(dir + "/coords.npy"); // [N,3]
        auto camera = npy::load(dir + "/camera.npy"); // [angle,distance,scale,image_res,grid_res]
        if (fmap.shape.size() != 3 || coords.shape.size() != 2 || coords.shape[1] != 3 ||
            camera.shape != std::vector<int64_t>{5}) throw std::invalid_argument("fixture shape mismatch");
        for (float value : camera.data)
            if (!std::isfinite(value)) throw std::invalid_argument("non-finite fixture camera");
        if (camera.data[3] < 1 || camera.data[3] > 16384 || std::floor(camera.data[3]) != camera.data[3] ||
            camera.data[4] < 2 || camera.data[4] > 256 || std::floor(camera.data[4]) != camera.data[4])
            throw std::invalid_argument("fixture camera dimensions out of bounds");
        const int height = fmap.shape[0], width = fmap.shape[1], channels = fmap.shape[2];
        if (height < 1 || width < 1 || channels < 1 || channels > 4096 || height > 2048 || width > 2048)
            throw std::invalid_argument("fixture dimensions out of bounds");
        std::vector<std::array<int,3>> points;
        for (size_t i = 0; i < coords.data.size(); i += 3) {
            std::array<int,3> point;
            for (int axis = 0; axis < 3; ++axis) {
                const float value = coords.data[i+axis];
                if (!std::isfinite(value) || value < 0 || value > 255 || std::floor(value) != value)
                    throw std::invalid_argument("fixture coordinates must be integer grid indices");
                point[axis] = int(value);
            }
            points.push_back(point);
        }
        using namespace mediaforge::pixal;
        auto plan = project_front_view(points, int(camera.data[4]), width, height,
                                      {camera.data[0],camera.data[1],camera.data[2],int(camera.data[3])});
        std::unique_ptr<ggml_context, decltype(&ggml_free)> ctx(
            ggml_init({ggml_tensor_overhead()*256 + ggml_graph_overhead(), nullptr, true}), ggml_free);
        if (!ctx) throw std::runtime_error("cannot allocate GGML context");
        auto* input = ggml_new_tensor_2d(ctx.get(), GGML_TYPE_F32, channels, int64_t(width)*height);
        ggml_set_input(input);
        auto projection = build_projection(ctx.get(), input, width, height, points.size());
        ggml_set_output(projection.result);
        auto* graph = ggml_new_graph(ctx.get());
        ggml_build_forward_expand(graph, projection.result);
        std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(
            kind == "cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(std::stoi(argv[3])),
            ggml_backend_free);
        if (!backend) throw std::runtime_error("requested backend unavailable");
        auto* device = ggml_backend_get_device(backend.get());
        for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
            if (!ggml_backend_dev_supports_op(device, ggml_graph_node(graph, i)))
                throw std::runtime_error("requested backend cannot execute every projection operation");
        }
        std::unique_ptr<ggml_backend_buffer, decltype(&ggml_backend_buffer_free)> buffer(
            ggml_backend_alloc_ctx_tensors(ctx.get(), backend.get()), ggml_backend_buffer_free);
        if (!buffer) throw std::runtime_error("cannot allocate projection tensors");
        ggml_backend_tensor_set(input, fmap.data.data(), 0, fmap.data.size()*sizeof(float));
        upload_projection(projection, plan);
        if (ggml_backend_graph_compute(backend.get(), graph) != GGML_STATUS_SUCCESS)
            throw std::runtime_error("projection computation failed");
        std::vector<float> result(points.size()*channels);
        ggml_backend_tensor_get(projection.result, result.data(), 0, result.size()*sizeof(float));
        npy::save(dir + "/actual.npy", result.data(), {int64_t(points.size()), channels});
        std::cout << "backend=" << ggml_backend_name(backend.get()) << " points=" << points.size() << '\n';
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }
}
