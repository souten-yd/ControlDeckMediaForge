#pragma once
#include "stage_bridge.h"

namespace mediaforge::pixal {
struct SsDecoderParams {
    int latent_channels=8, out_channels=1, res_blocks=2, middle_blocks=2;
    std::vector<int> channels{512,128,32};
    std::string norm_type="layer";
    bool reference_fp16=false;
};
struct SsDecoderCheckpoint { SsDecoderParams params; std::string storage, source_kind; };
SsDecoderCheckpoint inspect_ss_decoder_checkpoint(const std::string& path);
class SsDecoderModel {
public:
    SsDecoderModel(const std::string& path,ggml_backend* backend);
    ~SsDecoderModel();
    SsDecoderModel(const SsDecoderModel&)=delete;
    SsDecoderModel& operator=(const SsDecoderModel&)=delete;
    const trellis::Model& weights() const;
    const SsDecoderCheckpoint& spec() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
struct SsDecoderOptions {
    // The current graph computes in F32. A reference config using FP16 torso
    // activations requires explicit opt-in to F32 evaluation, never silent upcast.
    bool f32_arithmetic=false;
    CancelCheck cancelled;
    Progress progress;
};
struct SsDecoderStats { std::vector<size_t> segment_graph_bytes; };
struct Occupancy { int resolution; std::vector<float> logits; };
Occupancy decode_structure(const SsDecoderModel& model,const DenseLatent& latent,
    const SsDecoderOptions& options={},SsDecoderStats* stats=nullptr,
    std::map<std::string,std::vector<float>>* debug=nullptr);
// Actual SS flow -> decoder -> max-pool/coordinates; no supplied logits path.
Coordinates sample_sparse_structure(const FlowModel& flow,const SsDecoderModel& decoder,
    const ImageFeatures& image,const Camera& camera,const std::vector<float>& noise,int output_resolution,
    const StageOptions& flow_options={},const SsDecoderOptions& decoder_options={},SsDecoderStats* stats=nullptr,
    std::map<std::string,std::vector<float>>* debug=nullptr);
}
