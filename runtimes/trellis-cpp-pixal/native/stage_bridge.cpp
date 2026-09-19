#include "stage_bridge.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mediaforge::pixal {
namespace {
void check_cancel(const StageOptions& options) {
    if (options.cancelled && options.cancelled()) throw std::runtime_error("Pixal stage cancelled");
}
void finite(const std::vector<float>& values) {
    if (!std::all_of(values.begin(), values.end(), [](float v) { return std::isfinite(v); }))
        throw std::invalid_argument("non-finite latent or occupancy value");
}
void check_norm(const LatentNormalization& n, int channels) {
    if (channels < 1 || channels > 4096 || n.mean.size()!=size_t(channels) || n.std.size()!=size_t(channels))
        throw std::invalid_argument("latent normalization channel mismatch");
    finite(n.mean); finite(n.std);
    for (float v : n.std) if (v<=0) throw std::invalid_argument("latent normalization std must be positive");
}
void check_coords(const Coordinates& coords, int grid) {
    if (coords.empty() || coords.size()>1048576 || grid<2 || grid>512)
        throw std::invalid_argument("invalid sparse latent extent");
    for (const auto& c : coords) for (int v : c) if (v<0 || v>=grid)
        throw std::invalid_argument("sparse coordinate outside actual grid");
}
std::vector<float> transform(const std::vector<float>& values, const LatentNormalization& n, bool inverse) {
    check_norm(n,int(n.mean.size()));
    if (values.empty() || values.size()%n.mean.size()) throw std::invalid_argument("invalid latent normalization extent");
    finite(values);
    std::vector<float> result(values.size());
    for (size_t i=0;i<values.size();++i) {
        size_t c=i%n.mean.size();
        if (inverse) {
            // Keep separate F32 mul/add like the reference eager tensor ops.
            const float scaled=values[i]*n.std[c]; result[i]=scaled+n.mean[c];
        } else result[i]=(values[i]-n.mean[c])/n.std[c];
    }
    finite(result); return result;
}
std::vector<float> run(const FlowModel& model, const ImageFeatures& image, const FeatureMap* high,
    const Camera& camera, const Coordinates& coords, int grid, const std::vector<float>& noise,
    const std::vector<float>& concat, const StageOptions& options) {
    check_cancel(options); check_coords(coords,grid);
    const int channels=model.spec().params.out_ch;
    if (noise.size()!=coords.size()*size_t(channels)) throw std::invalid_argument("stage noise extent mismatch");
    finite(noise);
    auto pair=image_conditions(model.weights().backend,image,coords,grid,camera,high);
    check_cancel(options);
    FlowRunner runner(model,coords,int(image.global.size()/image.patches.channels),options.f32_weight_arithmetic);
    auto forward=[&](const std::vector<float>& x,float t,const FlowCondition& condition) { return runner.forward(x,t,condition,concat); };
    return sample_flow(forward,noise,pair.positive,pair.negative,options.sampler,
        model.spec().stage!="ss",channels,options.trace,options.cancelled,options.progress);
}
}
std::vector<float> normalize_latent(const std::vector<float>& v,const LatentNormalization& n) { return transform(v,n,false); }
std::vector<float> denormalize_latent(const std::vector<float>& v,const LatentNormalization& n) { return transform(v,n,true); }

Coordinates occupancy_coordinates(const std::vector<float>& logits,int decoded,int output) {
    if (decoded<2 || decoded>512 || output<2 || output>decoded || decoded%output ||
        logits.size()!=size_t(decoded)*decoded*decoded) throw std::invalid_argument("invalid occupancy cube or pooling ratio");
    finite(logits);
    int ratio=decoded/output;
    Coordinates result;
    for (int x=0;x<output;++x) for (int y=0;y<output;++y) for (int z=0;z<output;++z) {
        bool active=false;
        for (int dx=0;dx<ratio && !active;++dx) for (int dy=0;dy<ratio && !active;++dy) for (int dz=0;dz<ratio;++dz)
            if (logits[(size_t(x*ratio+dx)*decoded+y*ratio+dy)*decoded+z*ratio+dz]>0) { active=true; break; }
        if (active) result.push_back({x,y,z});
    }
    return result;
}
CascadePlan plan_shape_cascade(const Coordinates& decoder_coords,int requested,size_t max_tokens) {
    if ((requested!=1024 && requested!=1536) || max_tokens<1 || max_tokens>1048576 ||
        decoder_coords.empty() || decoder_coords.size()>size_t(512)*512*512)
        throw std::invalid_argument("invalid cascade resolution, token budget or decoder coordinates");
    for (const auto& c:decoder_coords) for (int v:c) if (v<0 || v>=512)
        throw std::invalid_argument("cascade decoder coordinate outside 512 grid");
    CascadePlan result{requested,requested,{}, {},false};
    for (;;) {
        int grid=result.actual_resolution/16;
        result.coords.clear(); result.coords.reserve(decoder_coords.size());
        for (const auto& c:decoder_coords) {
            std::array<int,3> q;
            for (int axis=0;axis<3;++axis) {
                float scaled=(float(c[axis])+.5f)/512.f*float(grid-1);
                int whole=int(std::floor(scaled)); float fraction=scaled-float(whole);
                q[axis]=whole+(fraction>.5f || (fraction==.5f && whole%2!=0));
            }
            result.coords.push_back(q);
        }
        std::sort(result.coords.begin(),result.coords.end());
        result.coords.erase(std::unique(result.coords.begin(),result.coords.end()),result.coords.end());
        result.attempts.push_back({result.actual_resolution,result.coords.size()});
        result.budget_met=result.coords.size()<max_tokens;
        if (result.budget_met || result.actual_resolution==1024) break;
        result.actual_resolution-=128;
    }
    return result;
}
DenseLatent sample_structure_latent(const FlowModel& model,const ImageFeatures& image,const Camera& camera,
    const std::vector<float>& noise,const StageOptions& options) {
    if (model.spec().stage!="ss") throw std::invalid_argument("SS stage requires an SS checkpoint");
    const int resolution=model.spec().resolution, channels=model.spec().params.out_ch;
    auto coords=dense_coordinates(resolution);
    auto sample=run(model,image,nullptr,camera,coords,resolution,noise,{},options);
    DenseLatent result{resolution,channels,std::vector<float>(sample.size())};
    for (size_t i=0;i<coords.size();++i) for (int c=0;c<channels;++c)
        result.values[size_t(c)*coords.size()+i]=sample[i*channels+c];
    return result;
}
SparseLatent sample_shape_latent(const FlowModel& model,const ImageFeatures& image,const FeatureMap* high,
    const Camera& camera,const Coordinates& coords,int grid,const std::vector<float>& noise,
    const LatentNormalization& norm,const StageOptions& options) {
    if (model.spec().stage!="shape") throw std::invalid_argument("shape stage requires a shape checkpoint");
    check_norm(norm,model.spec().params.out_ch);
    auto sample=run(model,image,high,camera,coords,grid,noise,{},options);
    return {coords,grid,model.spec().params.out_ch,denormalize_latent(sample,norm)};
}
SparseLatent sample_texture_latent(const FlowModel& model,const ImageFeatures& image,const FeatureMap* high,
    const Camera& camera,const SparseLatent& shape,const std::vector<float>& noise,
    const LatentNormalization& shape_norm,const LatentNormalization& texture_norm,const StageOptions& options) {
    if (model.spec().stage!="texture") throw std::invalid_argument("texture stage requires a texture checkpoint");
    check_norm(shape_norm,shape.channels); check_norm(texture_norm,model.spec().params.out_ch);
    check_coords(shape.coords,shape.grid_resolution);
    if (shape.channels!=model.spec().params.in_ch-model.spec().params.out_ch ||
        shape.values.size()!=shape.coords.size()*size_t(shape.channels)) throw std::invalid_argument("texture shape conditioning extent mismatch");
    check_cancel(options);
    auto concat=normalize_latent(shape.values,shape_norm);
    auto sample=run(model,image,high,camera,shape.coords,shape.grid_resolution,noise,concat,options);
    return {shape.coords,shape.grid_resolution,model.spec().params.out_ch,denormalize_latent(sample,texture_norm)};
}
}
