#pragma once
#include "flow_checkpoint.h"
#include "trellis_model.h"
#include <array>
#include <functional>
#include <memory>
#include <vector>

namespace mediaforge::pixal {
// All feature/latent vectors are token-major, with contiguous channels.
struct FlowCondition { std::vector<float> global, projected; };
struct FlowSamplerParams {
    int steps = 12;
    double rescale_t = 1, sigma_min = 1e-5;
    double guidance_strength = 7.5, guidance_rescale = 0;
    double interval_start = 0.6, interval_end = 1;
};
struct FlowStep {
    double t, t_previous;
    std::vector<float> velocity, predicted_clean, sample;
};
using FlowForward = std::function<std::vector<float>(const std::vector<float>&, float, const FlowCondition&)>;
using CancelCheck = std::function<bool()>;
using Progress = std::function<void(int, int)>;

// Backend is borrowed and must outlive model and every runner. No enumeration,
// fallback, or device selection happens here. Caller owns the genuine lease.
class FlowModel {
public:
    FlowModel(const std::string& path, ggml_backend* backend);
    ~FlowModel();
    FlowModel(const FlowModel&) = delete;
    FlowModel& operator=(const FlowModel&) = delete;
    const trellis::Model& weights() const;
    const FlowCheckpoint& spec() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

// One allocated graph reused for every forward. Coordinates must be in latent
// grid units, in exactly the same order as projected features/latent rows.
class FlowRunner {
public:
    FlowRunner(const FlowModel& model, const std::vector<std::array<int,3>>& coords,
               int global_tokens, bool f32_weight_arithmetic = false);
    ~FlowRunner();
    FlowRunner(const FlowRunner&) = delete;
    FlowRunner& operator=(const FlowRunner&) = delete;
    std::vector<float> forward(const std::vector<float>& latent, float t_scaled,
                              const FlowCondition& condition,
                              const std::vector<float>& concat_condition = {});
    size_t graph_bytes() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

std::vector<std::array<int,3>> dense_coordinates(int resolution);
// sparse=true preserves the reference SparseTensor population-moment std;
// dense uses torch's corrected std. Ratios are NOT clamped or silently repaired.
std::vector<float> sample_flow(const FlowForward& forward, std::vector<float> noise,
                              const FlowCondition& positive, const FlowCondition& negative,
                              const FlowSamplerParams& params, bool sparse, int channels,
                              std::vector<FlowStep>* trace = nullptr,
                              const CancelCheck& cancelled = {}, const Progress& progress = {});
}
