#pragma once
#include "image_features.h"

namespace mediaforge::pixal {
using Coordinates = std::vector<std::array<int,3>>;
struct LatentNormalization { std::vector<float> mean, std; };
struct SparseLatent {
    Coordinates coords;
    int grid_resolution, channels;
    std::vector<float> values; // token-major, decoder space after unnormalization
};
struct DenseLatent {
    int resolution, channels;
    std::vector<float> values; // [C,X,Y,Z], Z fastest, for the SS decoder
};
struct CascadeAttempt { int resolution; size_t tokens; };
struct CascadePlan {
    int requested_resolution, actual_resolution;
    Coordinates coords;
    std::vector<CascadeAttempt> attempts;
    bool budget_met;
};
struct StageOptions {
    FlowSamplerParams sampler;
    bool f32_weight_arithmetic = false;
    std::vector<FlowStep>* trace = nullptr; // sampler space, before normalization
    CancelCheck cancelled;
    Progress progress;
};

// Neural decoder output is supplied explicitly, never replaced by a heuristic.
Coordinates occupancy_coordinates(const std::vector<float>& logits, int decoded_resolution, int output_resolution);
// Matches actual Pixal run(): round((xyz+.5)/512*(grid-1)), sorted unique,
// strict token budget with 128-pixel backoff, stop at 1024 even if over budget.
CascadePlan plan_shape_cascade(const Coordinates& decoder_coords, int requested_resolution, size_t max_tokens);
std::vector<float> normalize_latent(const std::vector<float>& values, const LatentNormalization& normalization);
std::vector<float> denormalize_latent(const std::vector<float>& values, const LatentNormalization& normalization);

// Noise is explicit in token-major order. The caller owns seeded RNG provenance,
// checkpoint loading, decoder calls, image feature lifetime and backend lease.
DenseLatent sample_structure_latent(const FlowModel& model, const ImageFeatures& image,
    const Camera& camera, const std::vector<float>& noise, const StageOptions& options = {});
SparseLatent sample_shape_latent(const FlowModel& model, const ImageFeatures& image,
    const FeatureMap* high, const Camera& camera, const Coordinates& coords, int grid_resolution,
    const std::vector<float>& noise, const LatentNormalization& shape_norm, const StageOptions& options = {});
SparseLatent sample_texture_latent(const FlowModel& model, const ImageFeatures& image,
    const FeatureMap* high, const Camera& camera, const SparseLatent& shape,
    const std::vector<float>& noise, const LatentNormalization& shape_norm,
    const LatentNormalization& texture_norm, const StageOptions& options = {});
// Preprojected conditions avoid retaining dense high-resolution feature maps.
// Both condition branches are validated against the model before execution.
SparseLatent sample_shape_latent_conditioned(const FlowModel& model,const ConditionPair& conditions,
    const Coordinates& coords,int grid_resolution,const std::vector<float>& noise,
    const LatentNormalization& shape_norm,const StageOptions& options = {});
SparseLatent sample_texture_latent_conditioned(const FlowModel& model,const ConditionPair& conditions,
    const SparseLatent& shape,const std::vector<float>& noise,
    const LatentNormalization& shape_norm,const LatentNormalization& texture_norm,const StageOptions& options = {});
}
