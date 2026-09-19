// Pixal3D projection port. See ../NOTICE for upstream attribution.
#pragma once
#include <array>
#include <cstdint>
#include <vector>

struct ggml_context;
struct ggml_tensor;

namespace mediaforge::pixal {

struct Camera {
    float angle_x;
    float distance;
    float mesh_scale;
    int image_resolution;
};

// Front-view single-image projection, matching upstream ProjGrid. Coordinates
// are integer (x,y,z) grid indices, including sparse token order and repeats.
// A dense grid uses x outermost and z innermost, as torch.meshgrid(indexing='ij').
struct ProjectionPlan {
    int width;
    int height;
    std::array<std::vector<int32_t>, 4> indices;
    std::array<std::vector<float>, 4> weights;
};

ProjectionPlan project_front_view(const std::vector<std::array<int, 3>>& coords,
                                 int grid_resolution, int width, int height,
                                 const Camera& camera);

struct ProjectionInputs {
    std::array<ggml_tensor*, 4> indices;
    std::array<ggml_tensor*, 4> weights;
    ggml_tensor* result;
};

// fmap: contiguous F32 [channels, width*height], pixel order y*width+x.
// Builds get_rows/mul/add only; those operations exist on GGML CPU and Vulkan.
// The caller allocates this graph on its selected backend and uploads the plan
// to the returned input tensors. No backend selection or CPU fallback is hidden.
ProjectionInputs build_projection(ggml_context* ctx, ggml_tensor* fmap,
                                  int width, int height, int64_t count);
void upload_projection(const ProjectionInputs& inputs, const ProjectionPlan& plan);

} // namespace mediaforge::pixal
