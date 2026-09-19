#pragma once
#include "ss_decoder.h"
#include "surface_export.h"
#include "vision_checkpoint.h"

namespace mediaforge::pixal {
struct PipelineModels {
    std::string dino,naf,ss_flow,ss_decoder,shape_lr_flow,shape_hr_flow,shape_decoder,texture_flow,texture_decoder;
};
struct PipelineFrames {
    // Pillow/foreground processing is worker-owned; these are framed RGB CHW.
    std::vector<float> low,high;
    int low_size=512,high_size=1024;
};
using PipelineProgress=std::function<void(const std::string&,int,int)>;
using PipelineDiagnostic=std::function<void(const std::string&,const std::vector<float>&)>;
using PipelineNoise=std::function<std::vector<float>(const std::string&,size_t,int)>;
struct PipelineOptions {
    int resolution=1536;
    size_t max_tokens=49152;
    bool f32_arithmetic=false;
    uint32_t seed=42;
    // Reduced targets are explicit evaluation settings, never automatic fallback.
    int naf_lr=512,naf_hr=512,naf_texture=1024;
    // Pinned inference.py / deployed pipeline.json defaults.
    FlowSamplerParams ss_sampler{12,5.,1e-5,7.5,.7,.6,1.};
    FlowSamplerParams shape_sampler{12,3.,1e-5,7.5,.5,.6,1.};
    FlowSamplerParams texture_sampler{12,3.,1e-5,1.,0.,.6,.9};
    SparseDecoderOptions decoder;
    MeshDecodeOptions mesh;
    SurfaceExportOptions surface;
    CancelCheck cancelled;
    PipelineProgress progress;
    PipelineDiagnostic diagnostic;
};
struct PipelineResult {
    int actual_resolution=0;
    size_t ss_tokens=0,upsampled_tokens=0,hr_tokens=0;
    bool token_budget_met=false;
    std::string source_kind,rng_algorithm;
    std::vector<CascadeAttempt> attempts;
    SurfaceExportStats surface;
};
// Inspect all metadata/tensor tables and cross-model contracts before allocation.
// Returns synthetic or checkpoint; mixed provenance is rejected.
std::string inspect_pipeline(const PipelineModels& models);
// One borrowed, explicitly admitted backend. Models are loaded/released by stage.
// Supplied noise is useful for exact reference comparisons. The default RNG is
// mt19937 Box-Muller, versioned in the result; it is NOT Torch seed-equivalent.
// Caller owns model-hash admission, allowed paths, bounded process and Host lease.
PipelineResult generate_glb(const PipelineModels& models,ggml_backend* backend,const PipelineFrames& frames,
    const Camera& camera,const LatentNormalization& shape_norm,const LatentNormalization& texture_norm,
    const std::string& destination,const SurfaceProvenance& provenance,const PipelineOptions& options={},
    const PipelineNoise& noise={});
}
