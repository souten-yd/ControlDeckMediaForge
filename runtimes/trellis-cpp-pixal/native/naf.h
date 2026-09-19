#pragma once
#include "image_features.h"
#include <functional>

namespace mediaforge::pixal {
// Evaluation-only architecture of the pinned NAF. No training augmentation,
// hidden backend choice, network/model loader or automatic CPU fallback.
struct NafParams {
    int channels=256, heads=4, rope_heads=4, layers=2, kernel=9;
    int tile_pixels=128;
    bool f32_weight_arithmetic=false;
};
struct NafStats {
    size_t encoder_graph_bytes=0, attention_graph_bytes=0;
    int tiles=0, guide_width=0, guide_height=0;
};
FeatureMap upsample_naf(const trellis::Model& model, const NafParams& params,
                        const std::vector<float>& rgb_chw, int image_width, int image_height,
                        const FeatureMap& low, int output_width, int output_height,
                        NafStats* stats=nullptr,
                        std::map<std::string,std::vector<float>>* debug=nullptr,
                        const std::function<bool()>& cancelled={});
}
