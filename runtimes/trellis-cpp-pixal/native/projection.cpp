// Pixal3D ProjGrid port. See ../NOTICE for upstream attribution.
#include "projection.h"
#include "ggml.h"
#include "ggml-backend.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace mediaforge::pixal {

ProjectionPlan project_front_view(const std::vector<std::array<int, 3>>& coords,
                                 int resolution, int width, int height,
                                 const Camera& camera) {
    if (resolution < 2 || resolution > 256 || width < 1 || height < 1 ||
        int64_t(width) * height > std::numeric_limits<int32_t>::max() ||
        coords.empty() || coords.size() > 16777216 ||
        !std::isfinite(camera.angle_x) || camera.angle_x <= 0 || camera.angle_x >= 3.14159265f ||
        !std::isfinite(camera.distance) || camera.distance <= 0 ||
        !std::isfinite(camera.mesh_scale) || camera.mesh_scale <= 0 ||
        camera.image_resolution < 1) {
        throw std::invalid_argument("invalid Pixal3D front-view projection parameters");
    }
    ProjectionPlan plan{width, height, {}, {}};
    for (auto& v : plan.indices) v.reserve(coords.size());
    for (auto& v : plan.weights) v.reserve(coords.size());
    const float image_res = float(camera.image_resolution);
    const float focal = (16.0f / std::tan(camera.angle_x / 2.0f)) * image_res / 32.0f;
    for (const auto& coord : coords) {
        std::array<float, 3> point;
        for (int axis = 0; axis < 3; ++axis) {
            if (coord[axis] < 0 || coord[axis] >= resolution)
                throw std::invalid_argument("Pixal3D grid coordinate is outside the grid");
            point[axis] = (-1.0f + 2.0f * float(coord[axis]) / float(resolution - 1))
                          / camera.mesh_scale / 2.0f;
        }
        // Upstream rotates grid and camera into Blender coordinates. Applying
        // that camera's inverse cancels their common rotation. Keep the exact
        // pixel-center normalization (+0.5), align_corners=False and border
        // padding. Upstream computes but DOES NOT APPLY a visibility mask.
        const float depth = camera.distance - point[2];
        const float xp = focal * point[0] / (depth + 1e-8f) + image_res / 2.0f;
        const float yp = -focal * point[1] / (depth + 1e-8f) + image_res / 2.0f;
        const float nx = (xp + 0.5f) / image_res * 2.0f - 1.0f;
        const float ny = (yp + 0.5f) / image_res * 2.0f - 1.0f;
        const float px = std::clamp(((nx + 1.0f) * width - 1.0f) / 2.0f, 0.0f, float(width - 1));
        const float py = std::clamp(((ny + 1.0f) * height - 1.0f) / 2.0f, 0.0f, float(height - 1));
        if (!std::isfinite(px) || !std::isfinite(py))
            throw std::invalid_argument("non-finite Pixal3D projection");
        const int x0 = int(std::floor(px)), y0 = int(std::floor(py));
        const int x1 = std::min(x0 + 1, width - 1), y1 = std::min(y0 + 1, height - 1);
        const float dx = px - x0, dy = py - y0;
        const std::array<int32_t, 4> indices{y0 * width + x0, y0 * width + x1,
                                            y1 * width + x0, y1 * width + x1};
        const std::array<float, 4> weights{(1-dx)*(1-dy), dx*(1-dy), (1-dx)*dy, dx*dy};
        for (int i = 0; i < 4; ++i) {
            plan.indices[i].push_back(indices[i]);
            plan.weights[i].push_back(weights[i]);
        }
    }
    return plan;
}

ProjectionInputs build_projection(ggml_context* ctx, ggml_tensor* fmap,
                                  int width, int height, int64_t count) {
    if (!ctx || !fmap || width < 1 || height < 1 || count < 1 || count > 16777216 ||
        fmap->type != GGML_TYPE_F32 || !ggml_is_contiguous(fmap) ||
        fmap->ne[1] != int64_t(width) * height || fmap->ne[2] != 1 || fmap->ne[3] != 1)
        throw std::invalid_argument("invalid Pixal3D projection feature tensor");
    ProjectionInputs inputs{};
    for (int i = 0; i < 4; ++i) {
        inputs.indices[i] = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, count);
        inputs.weights[i] = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, 1, count);
        ggml_set_input(inputs.indices[i]);
        ggml_set_input(inputs.weights[i]);
        auto* sample = ggml_get_rows(ctx, fmap, inputs.indices[i]);
        auto* weighted = ggml_mul(ctx, sample, inputs.weights[i]);
        inputs.result = i == 0 ? weighted : ggml_add(ctx, inputs.result, weighted);
    }
    ggml_set_name(inputs.result, "pixal.projected_features");
    return inputs;
}

void upload_projection(const ProjectionInputs& inputs, const ProjectionPlan& plan) {
    for (int i = 0; i < 4; ++i) {
        if (plan.indices[i].size() != size_t(inputs.indices[i]->ne[0]) ||
            plan.weights[i].size() != size_t(inputs.weights[i]->ne[1]))
            throw std::invalid_argument("Pixal3D projection plan size mismatch");
        ggml_backend_tensor_set(inputs.indices[i], plan.indices[i].data(), 0,
                                plan.indices[i].size() * sizeof(int32_t));
        ggml_backend_tensor_set(inputs.weights[i], plan.weights[i].data(), 0,
                                plan.weights[i].size() * sizeof(float));
    }
}

} // namespace mediaforge::pixal
