#pragma once
#include "stage_bridge.h"

namespace mediaforge::pixal {
struct SparseDecoderParams {
    std::string kind;
    int latent_channels=32, out_channels=7, resolution=256;
    std::vector<int> channels, blocks, mlp_channels;
    bool reference_fp16=false;
    float voxel_margin=.5f;
};
struct SparseDecoderCheckpoint { SparseDecoderParams params; std::string storage,source_kind; };
SparseDecoderCheckpoint inspect_sparse_decoder_checkpoint(const std::string& path);
class SparseDecoderModel {
public:
    SparseDecoderModel(const std::string& path,ggml_backend* backend);
    ~SparseDecoderModel();
    SparseDecoderModel(const SparseDecoderModel&)=delete;
    SparseDecoderModel& operator=(const SparseDecoderModel&)=delete;
    const trellis::Model& weights() const;
    const SparseDecoderCheckpoint& spec() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
struct Subdivision { Coordinates coords; int grid_resolution; std::vector<float> logits; }; // [N,8], raw >0
struct SparseDecoderOptions {
    bool f32_arithmetic=false; // required explicit override for FP16 reference configs
    int chunk_rows=512;
    size_t max_voxels=64*1024*1024;
    CancelCheck cancelled;
    Progress progress;
};
// Individual graph/input-buffer maxima, not concurrent allocation or VRAM peaks.
struct SparseDecoderStats { size_t graph_peak_bytes=0, input_buffer_max_bytes=0, graph_executions=0; };
struct SparseDecodeResult { SparseLatent fields; std::vector<Subdivision> subdivisions; };
// Outputs are raw seven-channel dual-grid fields or six-channel PBR fields.
// No mesh/texture remap is implicit here. All row/coordinate orders are retained.
SparseDecodeResult decode_sparse(const SparseDecoderModel& model,const SparseLatent& latent,
    const std::vector<Subdivision>* guides=nullptr,const SparseDecoderOptions& options={},
    SparseDecoderStats* stats=nullptr,std::map<std::string,std::vector<float>>* debug=nullptr);
Coordinates upsample_shape(const SparseDecoderModel& model,const SparseLatent& latent,int times,
    const SparseDecoderOptions& options={},SparseDecoderStats* stats=nullptr);
}
