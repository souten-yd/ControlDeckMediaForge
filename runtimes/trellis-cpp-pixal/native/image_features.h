#pragma once
#include "flow_runner.h"
#include "projection.h"
#include <map>

namespace mediaforge::pixal {
// Plain-GELU DINOv3 ViT configuration. Defaults match the ViT-L/16 graph;
// small dimensions permit deterministic tests without pretrained weights.
struct DinoParams {
    int channels=1024, heads=16, layers=24, patch_size=16, registers=4, mlp_channels=4096;
    float norm_epsilon=1e-5f, rope_theta=100.f;
    bool f32_weight_arithmetic=false;
};
struct FeatureMap {
    int channels, width, height;
    std::vector<float> values; // [height,width,channels]
};
struct ImageFeatures {
    std::vector<float> global; // CLS followed by register tokens
    FeatureMap patches;
};
struct ConditionPair { FlowCondition positive, negative; };

// Input is resized/framed square RGB in [0,1], CHW. This applies ImageNet
// normalization. Backend is the one already owned by the caller's model.
ImageFeatures encode_dino(const trellis::Model& model, const DinoParams& params,
                          const std::vector<float>& rgb_chw, int image_size,
                          std::map<std::string,std::vector<float>>* debug = nullptr);
// Optional high_resolution is the ACTUAL NAF output, not an interpolation
// substitute. It is projected independently and concatenated after LR channels.
ConditionPair image_conditions(ggml_backend* backend, const ImageFeatures& features,
                               const std::vector<std::array<int,3>>& coords, int grid_resolution,
                               const Camera& camera, const FeatureMap* high_resolution = nullptr);
}
