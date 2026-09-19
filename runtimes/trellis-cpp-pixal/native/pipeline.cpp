#include "pipeline.h"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <random>
#include <stdexcept>

namespace mediaforge::pixal {
std::string inspect_pipeline(const PipelineModels& m) {
    auto d=inspect_vision_checkpoint(m.dino),n=inspect_vision_checkpoint(m.naf);
    auto ss=inspect_flow_checkpoint(m.ss_flow),lr=inspect_flow_checkpoint(m.shape_lr_flow),hr=inspect_flow_checkpoint(m.shape_hr_flow),tx=inspect_flow_checkpoint(m.texture_flow);
    auto sd=inspect_ss_decoder_checkpoint(m.ss_decoder);
    auto shape=inspect_sparse_decoder_checkpoint(m.shape_decoder),texture=inspect_sparse_decoder_checkpoint(m.texture_decoder);
    const auto& s=shape.params; const auto& t=texture.params;
    const int decoded_ss=ss.resolution*(1<<int(sd.params.channels.size()-1));
    if (d.kind!="dino" || n.kind!="naf" || ss.stage!="ss" || lr.stage!="shape" || hr.stage!="shape" || tx.stage!="texture" ||
        s.kind!="shape" || t.kind!="texture" || s.channels.size()!=5 || t.channels.size()!=5 ||
        ss.params.out_ch!=sd.params.latent_channels || decoded_ss<32 || decoded_ss%32 || lr.resolution!=32 || hr.resolution!=64 || tx.resolution!=64 ||
        lr.params.out_ch!=hr.params.out_ch || lr.params.out_ch!=s.latent_channels || tx.params.out_ch!=t.latent_channels ||
        tx.params.in_ch-tx.params.out_ch!=s.latent_channels)
        throw std::invalid_argument("pipeline model role/dimension/cascade mismatch");
    for (const auto* flow:{&ss,&lr,&hr,&tx}) {
        int projected=d.dino.channels*(flow==&ss?1:2);
        if (flow->params.d_cond!=d.dino.channels || flow->params.proj_in_channels!=projected)
            throw std::invalid_argument("pipeline image conditioning width mismatch");
    }
    for (const auto& kind:{n.source_kind,ss.source_kind,lr.source_kind,hr.source_kind,tx.source_kind,sd.source_kind,shape.source_kind,texture.source_kind})
        if (kind!=d.source_kind) throw std::invalid_argument("pipeline mixed source provenance");
    return d.source_kind;
}
namespace {
void finite(const std::vector<float>& values) {
    for (float x:values) if (!std::isfinite(x)) throw std::invalid_argument("non-finite pipeline input");
}
void norm(const LatentNormalization& n,int channels) {
    if (n.mean.size()!=size_t(channels) || n.std.size()!=size_t(channels)) throw std::invalid_argument("pipeline normalization dimensions");
    finite(n.mean);finite(n.std);
    for (float x:n.std) if (x<=0) throw std::invalid_argument("pipeline normalization std must be positive");
}
}
PipelineResult generate_glb(const PipelineModels& m,ggml_backend* backend,const PipelineFrames& frames,
    const Camera& camera,const LatentNormalization& sn,const LatentNormalization& tn,
    const std::string& destination,const SurfaceProvenance& provenance,const PipelineOptions& o,const PipelineNoise& supplied_noise) {
    auto cancelled=[&]() { return o.cancelled && o.cancelled(); };
    auto cancel=[&]() { if (cancelled()) throw std::runtime_error("Pixal pipeline cancelled"); };
    auto progress=[&](const std::string& name,int done,int total) { cancel(); if (o.progress) o.progress(name,done,total); cancel(); };
    cancel();
    if (!backend || (o.resolution!=1024 && o.resolution!=1536) || o.max_tokens<1 || o.max_tokens>1048576 || !o.surface.remesh || !o.mesh.require_faces)
        throw std::invalid_argument("invalid pipeline backend/resolution/budget/export mode");
    if (!std::isfinite(camera.angle_x) || !std::isfinite(camera.distance) || !std::isfinite(camera.mesh_scale) ||
        camera.angle_x<=0 || camera.angle_x>=3.14159265358979323846 || camera.distance<=0 || camera.mesh_scale<=0)
        throw std::invalid_argument("invalid pipeline camera");
    for (int target:{o.naf_lr,o.naf_hr,o.naf_texture}) if (target<1 || target>1024) throw std::invalid_argument("invalid pipeline NAF target");
    for (const auto& pair:{std::pair{frames.low_size,&frames.low},std::pair{frames.high_size,&frames.high}}) {
        if (pair.first<1 || pair.first>1024 || pair.second->size()!=size_t(pair.first)*pair.first*3) throw std::invalid_argument("invalid pipeline RGB frame");
        finite(*pair.second);for (float x:*pair.second) if (x<0 || x>1) throw std::invalid_argument("pipeline RGB outside unit range");
    }
    auto target=std::filesystem::path(destination);
    if (target.filename().empty() || target.filename()=="." || target.filename()=="..") throw std::invalid_argument("invalid pipeline output path");
    target=std::filesystem::canonical(target.parent_path())/target.filename();
    if (std::filesystem::symlink_status(target).type()!=std::filesystem::file_type::not_found) throw std::invalid_argument("pipeline output exists");
    for (const auto& sampler:{o.ss_sampler,o.shape_sampler,o.texture_sampler}) validate_flow_sampler(sampler);
    progress("inspect",0,1); PipelineResult result; result.source_kind=inspect_pipeline(m);
    if (result.source_kind!=provenance.source_kind || provenance.seed!=o.seed) throw std::invalid_argument("pipeline output provenance mismatch");
    auto lr_spec=inspect_flow_checkpoint(m.shape_lr_flow),tex_spec=inspect_flow_checkpoint(m.texture_flow);
    norm(sn,lr_spec.params.out_ch);norm(tn,tex_spec.params.out_ch);progress("inspect",1,1);
    result.rng_algorithm=supplied_noise?"provided-f32-v1":"mt19937-box-muller-f32-v1";
    std::mt19937 engine(o.seed);
    auto noise=[&](const std::string& stage,size_t rows,int channels) {
        cancel();if (rows==0 || rows>1048576 || channels<1 || channels>256) throw std::invalid_argument("pipeline noise budget exceeded");
        size_t count=rows*size_t(channels); std::vector<float> values;
        if (supplied_noise) values=supplied_noise(stage,rows,channels);
        else {
            values.resize(count);
            for (size_t i=0;i<count;i+=2) {
                double u=(double(engine())+.5)/4294967296.,v=(double(engine())+.5)/4294967296.;
                double radius=std::sqrt(-2*std::log(u)),angle=6.28318530717958647692*v;
                values[i]=float(radius*std::cos(angle));if (i+1<count) values[i+1]=float(radius*std::sin(angle));
            }
        }
        if (values.size()!=count) throw std::invalid_argument("pipeline noise extent mismatch");
        finite(values);cancel();return values;
    };
    auto diagnostic=[&](const std::string& name,const std::vector<float>& value) { if (o.diagnostic) o.diagnostic(name,value); cancel(); };
    auto coords_diagnostic=[&](const std::string& name,const Coordinates& coords) {
        if (!o.diagnostic) return;
        std::vector<float> values;values.reserve(coords.size()*3);
        for (const auto& c:coords) for (int v:c) values.push_back(float(v));
        diagnostic(name,values);
    };
    auto stage_options=[&](const std::string& name,const FlowSamplerParams& sampler,std::vector<FlowStep>& trace) {
        StageOptions stage;stage.sampler=sampler;stage.f32_weight_arithmetic=o.f32_arithmetic;stage.cancelled=cancelled;
        stage.progress=[&,name](int done,int total) { progress(name,done,total); };stage.trace=o.diagnostic?&trace:nullptr;return stage;
    };
    auto trace_diagnostic=[&](const std::string& name,const std::vector<FlowStep>& trace) {
        for (size_t i=0;i<trace.size();++i) diagnostic(name+".sample"+std::to_string(i),trace[i].sample);
    };
    auto vision=[&](const std::string& stage,const std::vector<float>& rgb,int size,int target) {
        progress(stage,0,1);VisionFeatures f;
        { VisionModel dino(m.dino,backend); std::unique_ptr<VisionModel> naf;
          if (target) naf=std::make_unique<VisionModel>(m.naf,backend);
          f=encode_vision(dino,naf.get(),rgb,size,target,target,o.f32_arithmetic,nullptr,nullptr,cancelled); }
        diagnostic(stage+".global",f.dino.global);diagnostic(stage+".patches",f.dino.patches.values);
        if (f.high) diagnostic(stage+".high",f.high->values);
        progress(stage,1,1);return f;
    };
    auto cam=[&](int size) { auto c=camera;c.image_resolution=size;return c; };
    auto dec=o.decoder;dec.f32_arithmetic=o.f32_arithmetic;
    dec.cancelled=[&]() { return cancelled() || (o.decoder.cancelled && o.decoder.cancelled()); };
    auto mesh=o.mesh;mesh.cancelled=[&]() { return cancelled() || (o.mesh.cancelled && o.mesh.cancelled()); };
    Coordinates coords;
    {
        DenseLatent dense;
        { auto features=vision("ss_image",frames.low,frames.low_size,0); std::vector<FlowStep> trace;
          { FlowModel flow(m.ss_flow,backend); int r=flow.spec().resolution;
            dense=sample_structure_latent(flow,features.dino,cam(frames.low_size),noise("ss",size_t(r)*r*r,flow.spec().params.out_ch),stage_options("ss_flow",o.ss_sampler,trace)); }
          trace_diagnostic("ss",trace); }
        diagnostic("ss_latent",dense.values);
        { progress("ss_decode",0,1); SsDecoderModel decoder(m.ss_decoder,backend);SsDecoderOptions options;
          options.f32_arithmetic=o.f32_arithmetic;options.cancelled=cancelled;
          options.progress=[&](int done,int total) { progress("ss_decode",done,total); };
          auto occupancy=decode_structure(decoder,dense,options);diagnostic("ss_logits",occupancy.logits);
          coords=occupancy_coordinates(occupancy.logits,occupancy.resolution,32); }
    }
    if (coords.empty()) throw std::runtime_error("pipeline SS decoder produced no coordinates");
    result.ss_tokens=coords.size();coords_diagnostic("ss_coords",coords);
    CascadePlan plan;
    {
        SparseLatent lr;
        { auto features=vision("lr_image",frames.low,frames.low_size,o.naf_lr); std::vector<FlowStep> trace;
          { FlowModel flow(m.shape_lr_flow,backend);
            lr=sample_shape_latent(flow,features.dino,&*features.high,cam(frames.low_size),coords,32,noise("lr",coords.size(),flow.spec().params.out_ch),sn,stage_options("lr_flow",o.shape_sampler,trace)); }
          trace_diagnostic("lr",trace); }
        diagnostic("lr",lr.values);
        Coordinates up;
        { progress("upsample",0,1);SparseDecoderModel decoder(m.shape_decoder,backend);
          dec.progress=[&](int done,int total) { progress("upsample",done,total); };
          up=upsample_shape(decoder,lr,4,dec); }
        result.upsampled_tokens=up.size();coords_diagnostic("upsampled_coords",up);
        progress("cascade",0,1);plan=plan_shape_cascade(up,o.resolution,o.max_tokens);progress("cascade",1,1);
    }
    coords.clear();coords.shrink_to_fit();
    result.actual_resolution=plan.actual_resolution;result.hr_tokens=plan.coords.size();result.token_budget_met=plan.budget_met;result.attempts=plan.attempts;
    coords_diagnostic("hr_coords",plan.coords);
    std::vector<float> attempts;for (const auto& attempt:plan.attempts) { attempts.push_back(float(attempt.resolution));attempts.push_back(float(attempt.tokens)); }
    diagnostic("cascade_attempts",attempts);
    SparseLatent shape,texture;
    { auto features=vision("hr_image",frames.high,frames.high_size,o.naf_hr);std::vector<FlowStep> trace;
      { FlowModel flow(m.shape_hr_flow,backend);
        shape=sample_shape_latent(flow,features.dino,&*features.high,cam(frames.high_size),plan.coords,plan.actual_resolution/16,noise("hr",plan.coords.size(),flow.spec().params.out_ch),sn,stage_options("hr_flow",o.shape_sampler,trace)); }
      trace_diagnostic("hr",trace); }
    plan.coords.clear();plan.coords.shrink_to_fit();diagnostic("hr",shape.values);
    { auto features=vision("texture_image",frames.high,frames.high_size,o.naf_texture);std::vector<FlowStep> trace;
      { FlowModel flow(m.texture_flow,backend);
        texture=sample_texture_latent(flow,features.dino,&*features.high,cam(frames.high_size),shape,noise("texture",shape.coords.size(),flow.spec().params.out_ch),sn,tn,stage_options("texture_flow",o.texture_sampler,trace)); }
      trace_diagnostic("texture",trace); }
    diagnostic("texture",texture.values);
    SparseDecodeResult decoded_shape;
    { progress("shape_decode",0,1);SparseDecoderModel decoder(m.shape_decoder,backend);
      dec.progress=[&](int done,int total) { progress("shape_decode",done,total); };
      decoded_shape=decode_sparse(decoder,shape,nullptr,dec); }
    shape={};
    if (decoded_shape.fields.grid_resolution!=result.actual_resolution) throw std::runtime_error("pipeline final decoder resolution mismatch");
    diagnostic("shape_fields",decoded_shape.fields.values);coords_diagnostic("decoded_coords",decoded_shape.fields.coords);
    SparseDecodeResult decoded_texture;
    { progress("texture_decode",0,1);SparseDecoderModel decoder(m.texture_decoder,backend);
      dec.progress=[&](int done,int total) { progress("texture_decode",done,total); };
      decoded_texture=decode_sparse(decoder,texture,&decoded_shape.subdivisions,dec); }
    texture={};
    if (decoded_texture.fields.coords!=decoded_shape.fields.coords || decoded_texture.fields.grid_resolution!=decoded_shape.fields.grid_resolution)
        throw std::runtime_error("pipeline final geometry/texture coordinates differ");
    diagnostic("texture_fields",decoded_texture.fields.values);
    UnrepairedSurface surface;
    { progress("mesh",0,1);mesh.progress=[&](int done,int total) { progress("mesh",done,total); };
      float margin=inspect_sparse_decoder_checkpoint(m.shape_decoder).params.voxel_margin;
      surface.mesh=mesh_from_fields(decoded_shape.fields,margin,mesh);surface.texture=pbr_from_fields(decoded_texture.fields,mesh); }
    decoded_shape={};decoded_texture={};diagnostic("pbr",surface.texture.values);
    if (o.diagnostic) {
        std::vector<float> vertices,faces;
        for (const auto& v:surface.mesh.vertices) vertices.insert(vertices.end(),v.begin(),v.end());
        for (const auto& f:surface.mesh.faces) for (int x:f) faces.push_back(float(x));
        diagnostic("vertices",vertices);diagnostic("faces",faces);
    }
    auto export_options=o.surface;
    export_options.cancelled=[&]() { return cancelled() || (o.surface.cancelled && o.surface.cancelled()); };
    export_options.phase=[&](const std::string& phase) { progress("surface_"+phase,0,1);if (o.surface.phase) o.surface.phase(phase);cancel(); };
    auto baked=bake_surface(surface,export_options);surface={};
    auto output_provenance=provenance;output_provenance.rng_algorithm=result.rng_algorithm;
    result.surface=export_surface_glb(baked,target.string(),output_provenance,export_options);
    // No cancellable callback after publication: the caller owns terminal status.
    return result;
}
}
