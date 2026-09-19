// Pixal3D flow execution using the pinned trellis.cpp DiT/GGML graph.
// GGUF loading/RoPE/timestep formula adapted from trellis.cpp (MIT, see NOTICE).
#include "flow_runner.h"
#include "ggml.h"
#include "gguf.h"
#include "ggml-backend.h"
#include "ggml-alloc.h"
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>

namespace mediaforge::pixal {
namespace {
void finite(const std::vector<float>& values, const char* label) {
    for (float value : values)
        if (!std::isfinite(value)) throw std::runtime_error(std::string("non-finite ") + label);
}
void check_cancel(const CancelCheck& cancelled) {
    if (cancelled && cancelled()) throw std::runtime_error("Pixal flow cancelled");
}
float standard_deviation(const std::vector<float>& x, bool sparse, int channels) {
    if (!sparse) {
        double mean = 0, variance = 0;
        for (float v : x) mean += v;
        mean /= x.size();
        for (float v : x) variance += (v-mean)*(v-mean);
        return float(std::sqrt(variance/(x.size()-1)));
    }
    // SparseTensor.std computes E[x^2] - E[x]^2, first over channels,
    // then over the tokens of each batch. This runner has batch size one.
    float mean = 0, square_mean = 0;
    const size_t count = x.size()/channels;
    for (size_t i = 0; i < count; ++i) {
        float row = 0, square_row = 0;
        for (int c = 0; c < channels; ++c) {
            float v = x[i*channels+c]; row += v; square_row += v*v;
        }
        mean += row/channels; square_mean += square_row/channels;
    }
    mean /= count; square_mean /= count;
    return std::sqrt(square_mean-mean*mean);
}
}

struct FlowModel::Impl {
    trellis::Model model;
    FlowCheckpoint checkpoint;
    ~Impl() { model.backend = nullptr; model.free(); } // borrowed backend
};
FlowModel::FlowModel(const std::string& path, ggml_backend* backend) : impl_(std::make_unique<Impl>()) {
    if (!backend) throw std::invalid_argument("explicit flow backend is required");
    auto& m = impl_->model;
    impl_->checkpoint = inspect_flow_checkpoint(path);
    gguf_init_params init{true, &m.meta};
    m.gguf = gguf_init_from_file(path.c_str(), init);
    if (!m.gguf || !m.meta) throw std::runtime_error("cannot load flow GGUF metadata");
    m.arch = "pixal3d-flow";
    m.backend = backend;
    m.on_gpu = ggml_backend_dev_type(ggml_backend_get_device(backend)) != GGML_BACKEND_DEVICE_TYPE_CPU;
    m.buffer = ggml_backend_alloc_ctx_tensors(m.meta, backend);
    if (!m.buffer) throw std::runtime_error("cannot allocate flow weights on selected backend");
    ggml_backend_buffer_set_usage(m.buffer, GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
    auto close_file = [](FILE* stream) { fclose(stream); };
    std::unique_ptr<FILE, decltype(close_file)> file(fopen(path.c_str(), "rb"), close_file);
    if (!file) throw std::runtime_error("cannot reopen flow GGUF");
    const size_t data_offset = gguf_get_data_offset(m.gguf);
    std::vector<uint8_t> staging;
    for (int64_t i = 0; i < gguf_get_n_tensors(m.gguf); ++i) {
        const auto* name = gguf_get_tensor_name(m.gguf, i);
        auto* tensor = ggml_get_tensor(m.meta, name);
        const size_t relative = gguf_get_tensor_offset(m.gguf, i);
        if (relative > size_t(std::numeric_limits<int64_t>::max())-data_offset)
            throw std::runtime_error("flow tensor offset overflow");
        staging.resize(ggml_nbytes(tensor));
        if (fseeko(file.get(), off_t(data_offset+relative), SEEK_SET) != 0 ||
            fread(staging.data(), 1, staging.size(), file.get()) != staging.size())
            throw std::runtime_error("short read of flow weight");
        ggml_backend_tensor_set(tensor, staging.data(), 0, staging.size());
        m.tensors[name] = tensor;
    }
}
FlowModel::~FlowModel() = default;
const trellis::Model& FlowModel::weights() const { return impl_->model; }
const FlowCheckpoint& FlowModel::spec() const { return impl_->checkpoint; }

struct FlowRunner::Impl {
    const FlowModel& model;
    ggml_context* ctx = nullptr;
    ggml_gallocr_t allocator = nullptr;
    ggml_cgraph* graph = nullptr;
    ggml_tensor *input, *timestep, *global, *projected, *cosine, *sine, *output;
    int tokens, global_tokens;
    std::vector<float> rcos, rsin;
    explicit Impl(const FlowModel& m) : model(m) {}
    ~Impl() { if (allocator) ggml_gallocr_free(allocator); if (ctx) ggml_free(ctx); }
};
std::vector<std::array<int,3>> dense_coordinates(int resolution) {
    if (resolution < 2 || resolution > 64) throw std::invalid_argument("invalid dense flow resolution");
    std::vector<std::array<int,3>> coords;
    coords.reserve(size_t(resolution)*resolution*resolution);
    for (int x=0; x<resolution; ++x) for (int y=0; y<resolution; ++y) for (int z=0; z<resolution; ++z)
        coords.push_back({x,y,z});
    return coords;
}
FlowRunner::FlowRunner(const FlowModel& model, const std::vector<std::array<int,3>>& coords,
                       int global_tokens, bool f32_weight_arithmetic) : impl_(std::make_unique<Impl>(model)) {
    auto& s = *impl_;
    auto p = model.spec().params;
    p.cast_f32 = f32_weight_arithmetic;
    if (coords.empty() || coords.size() > 1048576 || global_tokens < 1 || global_tokens > 4096)
        throw std::invalid_argument("invalid flow token count");
    if (model.spec().stage == "ss" && coords != dense_coordinates(model.spec().resolution))
        throw std::invalid_argument("SS flow requires the complete ordered dense grid");
    for (const auto& coord : coords) for (int v : coord)
        if (v < 0 || v > 4095) throw std::invalid_argument("invalid flow coordinate");
    s.tokens = int(coords.size()); s.global_tokens = global_tokens;
    const int half = p.head_dim/2, fd = half/3;
    for (const auto& coord : coords) for (int pair=0; pair<half; ++pair) {
        const float angle = pair < 3*fd ? coord[pair/fd] / std::pow(10000.f, float(pair%fd)/fd) : 0;
        s.rcos.push_back(std::cos(angle)); s.rsin.push_back(std::sin(angle));
    }
    s.ctx = ggml_init({ggml_tensor_overhead()*32768 + ggml_graph_overhead_custom(32768, false) + (1<<20), nullptr, true});
    if (!s.ctx) throw std::runtime_error("cannot allocate flow graph metadata");
    auto input = [&](int channels, int count) {
        auto* tensor = ggml_new_tensor_2d(s.ctx, GGML_TYPE_F32, channels, count);
        ggml_set_input(tensor); return tensor;
    };
    s.input = input(p.in_ch, s.tokens);
    s.timestep = input(256, 1);
    s.global = input(p.d_cond, global_tokens);
    s.projected = input(p.proj_in_channels, s.tokens);
    s.cosine = ggml_new_tensor_4d(s.ctx, GGML_TYPE_F32, 1, half, 1, s.tokens); ggml_set_input(s.cosine);
    s.sine = ggml_new_tensor_4d(s.ctx, GGML_TYPE_F32, 1, half, 1, s.tokens); ggml_set_input(s.sine);
    s.output = trellis::build_dit_dense(s.ctx, model.weights(), p, s.input, s.timestep,
                                       s.global, s.cosine, s.sine, nullptr, s.projected);
    ggml_set_output(s.output);
    s.graph = ggml_new_graph_custom(s.ctx, 32768, false);
    ggml_build_forward_expand(s.graph, s.output);
    const auto backend = model.weights().backend;
    for (int i=0; i<ggml_graph_n_nodes(s.graph); ++i)
        if (!ggml_backend_dev_supports_op(ggml_backend_get_device(backend), ggml_graph_node(s.graph, i)))
            throw std::runtime_error("selected backend cannot execute all flow graph operations");
    s.allocator = ggml_gallocr_new(ggml_backend_get_default_buffer_type(backend));
    if (!s.allocator || !ggml_gallocr_alloc_graph(s.allocator, s.graph))
        throw std::runtime_error("cannot allocate flow graph on selected backend");
}
FlowRunner::~FlowRunner() = default;
size_t FlowRunner::graph_bytes() const { return ggml_gallocr_get_buffer_size(impl_->allocator, 0); }
std::vector<float> FlowRunner::forward(const std::vector<float>& latent, float t_scaled,
                                     const FlowCondition& condition, const std::vector<float>& concat_condition) {
    auto& s = *impl_;
    const auto& p = s.model.spec().params;
    const bool texture = s.model.spec().stage == "texture";
    if (latent.size() != size_t(s.tokens)*p.out_ch ||
        concat_condition.size() != (texture ? latent.size() : 0) ||
        condition.global.size() != size_t(s.global_tokens)*p.d_cond ||
        condition.projected.size() != size_t(s.tokens)*p.proj_in_channels ||
        !std::isfinite(t_scaled) || t_scaled < 0 || t_scaled > 1000)
        throw std::invalid_argument("flow input/condition shape or timestep mismatch");
    finite(latent, "latent"); finite(concat_condition, "concat condition");
    finite(condition.global, "global condition"); finite(condition.projected, "projected condition");
    std::vector<float> joined;
    if (texture) {
        joined.reserve(size_t(s.tokens)*p.in_ch);
        for (int i=0; i<s.tokens; ++i) {
            joined.insert(joined.end(), latent.begin()+i*p.out_ch, latent.begin()+(i+1)*p.out_ch);
            joined.insert(joined.end(), concat_condition.begin()+i*p.out_ch, concat_condition.begin()+(i+1)*p.out_ch);
        }
    }
    std::vector<float> tf(256);
    for (int j=0; j<128; ++j) {
        const float angle = t_scaled*std::exp(-std::log(10000.f)*j/128.f);
        tf[j] = std::cos(angle); tf[j+128] = std::sin(angle);
    }
    auto upload = [](ggml_tensor* t, const std::vector<float>& values) {
        ggml_backend_tensor_set(t, values.data(), 0, values.size()*sizeof(float));
    };
    // gallocr can reuse input storage. Re-upload every input on EVERY forward,
    // including negative/positive projection and fixed texture shape data.
    upload(s.input, texture ? joined : latent); upload(s.timestep, tf);
    upload(s.global, condition.global); upload(s.projected, condition.projected);
    upload(s.cosine, s.rcos); upload(s.sine, s.rsin);
    if (ggml_backend_graph_compute(s.model.weights().backend, s.graph) != GGML_STATUS_SUCCESS)
        throw std::runtime_error("flow compute failed");
    auto result = trellis::tensor_to_f32(s.output);
    finite(result, "flow velocity");
    return result;
}

std::vector<float> sample_flow(const FlowForward& forward, std::vector<float> sample,
                              const FlowCondition& positive, const FlowCondition& negative,
                              const FlowSamplerParams& p, bool sparse, int channels,
                              std::vector<FlowStep>* trace, const CancelCheck& cancelled, const Progress& progress) {
    for (double value : {p.rescale_t, p.sigma_min, p.guidance_strength, p.guidance_rescale, p.interval_start, p.interval_end})
        if (!std::isfinite(value)) throw std::invalid_argument("non-finite sampler parameter");
    if (!forward || p.steps < 1 || p.steps > 1000 || p.rescale_t <= 0 || p.sigma_min < 0 || p.sigma_min >= 1 ||
        p.guidance_rescale < 0 || p.guidance_rescale > 1 || p.interval_start < 0 || p.interval_end > 1 ||
        p.interval_start > p.interval_end || channels < 1 || sample.size() < 2 || sample.size()%channels)
        throw std::invalid_argument("invalid flow sampler parameters");
    finite(sample, "initial noise");
    auto predict = [&](float scaled_t, const FlowCondition& cond) {
        check_cancel(cancelled);
        auto out = forward(sample, scaled_t, cond);
        check_cancel(cancelled);
        if (out.size() != sample.size()) throw std::invalid_argument("flow velocity size mismatch");
        finite(out, "flow velocity"); return out;
    };
    std::vector<double> times(p.steps+1);
    for (int i=0; i<=p.steps; ++i) {
        const double t = 1.0-double(i)/p.steps;
        times[i] = p.rescale_t*t/(1+(p.rescale_t-1)*t);
    }
    if (progress) progress(0, p.steps);
    for (int i=0; i<p.steps; ++i) {
        check_cancel(cancelled);
        const double t = times[i];
        const double guidance = (p.interval_start <= t && t <= p.interval_end) ? p.guidance_strength : 1;
        const float strength = float(guidance);
        const float a = float(1-p.sigma_min), b = float(p.sigma_min+(1-p.sigma_min)*t);
        std::vector<float> pred;
        if (guidance == 1) pred = predict(float(1000*t), positive);
        else if (guidance == 0) pred = predict(float(1000*t), negative);
        else {
            const auto pos = predict(float(1000*t), positive);
            const auto neg = predict(float(1000*t), negative);
            pred.resize(sample.size());
            for (size_t k=0; k<pred.size(); ++k) pred[k] = strength*pos[k]+float(1-guidance)*neg[k];
            if (p.guidance_rescale > 0) {
                std::vector<float> x_pos(sample.size()), x_cfg(sample.size());
                for (size_t k=0; k<sample.size(); ++k) {
                    x_pos[k] = a*sample[k]-b*pos[k]; x_cfg[k] = a*sample[k]-b*pred[k];
                }
                const float ratio = standard_deviation(x_pos, sparse, channels)/standard_deviation(x_cfg, sparse, channels);
                if (!std::isfinite(ratio)) throw std::runtime_error("non-finite CFG rescale ratio");
                for (size_t k=0; k<sample.size(); ++k) {
                    const float rescaled = x_cfg[k]*ratio;
                    const float clean = float(p.guidance_rescale)*rescaled+float(1-p.guidance_rescale)*x_cfg[k];
                    pred[k] = (a*sample[k]-clean)/b;
                }
            }
        }
        finite(pred, "guided velocity");
        std::vector<float> clean;
        if (trace) {
            clean.resize(sample.size());
            for (size_t k=0; k<sample.size(); ++k) clean[k] = a*sample[k]-b*pred[k];
            finite(clean, "predicted clean latent");
        }
        for (size_t k=0; k<sample.size(); ++k) sample[k] -= float(t-times[i+1])*pred[k];
        finite(sample, "sampled latent");
        if (trace) trace->push_back({t, times[i+1], pred, std::move(clean), sample});
        if (progress) progress(i+1, p.steps);
    }
    return sample;
}
}
