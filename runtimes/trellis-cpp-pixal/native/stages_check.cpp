// Trusted synthetic fixtures. Supplied decoder logits/upsampled coordinates
// exercise the decoder boundary; this driver does not perform neural decoding.
#include "stage_bridge.h"
#include "vision_checkpoint.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace pixal=mediaforge::pixal;
namespace trellis { extern bool g_no_fa; }
int main(int argc,char** argv) {
    try {
        if (argc<3) throw std::invalid_argument("usage: pixal-stages-check fixture cpu|vulkan [--device N] [--dino path --naf path --ss path --shape path --texture path] [--fault name]");
        std::string directory=argv[1],kind=argv[2];
        std::map<std::string,std::string> flags;
        for (int i=3;i<argc;++i) {
            std::string flag=argv[i];
            if (i+1>=argc || (flag!="--device" && flag!="--dino" && flag!="--naf" && flag!="--ss" && flag!="--shape" && flag!="--texture" && flag!="--fault"))
                throw std::invalid_argument("invalid stage fixture argument");
            flags[flag]=argv[++i];
        }
        const bool gpu=kind=="vulkan";
        if ((kind!="cpu" && !gpu) || gpu!=(flags.count("--device")!=0)) throw std::invalid_argument("explicit stage backend/device required");
        auto load=[&](const std::string& name) {
            auto a=npy::load(directory+"/"+name+".npy");
            if (a.numel()>4000000) throw std::invalid_argument("synthetic stage fixture too large");
            return a;
        };
        auto integer=[](float v) { if (!std::isfinite(v) || v!=std::floor(v) || std::abs(v)>10000000) throw std::invalid_argument("invalid fixture integer"); return int(v); };
        auto raw=load("decoder_coords"),settings=load("settings"),logits=load("logits");
        if (settings.data.size()!=4 || raw.shape.size()!=2 || raw.shape[1]!=3) throw std::invalid_argument("invalid bridge fixture dimensions");
        pixal::Coordinates decoder_coords;
        for (size_t i=0;i<raw.data.size();i+=3) decoder_coords.push_back({integer(raw.data[i]),integer(raw.data[i+1]),integer(raw.data[i+2])});
        std::string fault=flags["--fault"];
        if (fault=="nan_occupancy") logits.data[0]=std::numeric_limits<float>::quiet_NaN();
        if (fault=="occupancy_extent") logits.data.pop_back();
        if (fault=="pool_ratio") settings.data[1]=3;
        if (fault=="cascade_extent") decoder_coords[0][0]=512;
        if (fault=="cascade_resolution") settings.data[2]=512;
        if (fault=="cascade_budget") settings.data[3]=0;
        if (fault=="cascade_empty") decoder_coords.clear();
        auto coords=pixal::occupancy_coordinates(logits.data,integer(settings.data[0]),integer(settings.data[1]));
        auto plan=pixal::plan_shape_cascade(decoder_coords,integer(settings.data[2]),integer(settings.data[3]));
        std::map<std::string,std::vector<float>> debug;
        auto record_coords=[&](const std::string& label,const pixal::Coordinates& values) {
            auto& out=debug[label]; for (const auto& c:values) for (int v:c) out.push_back(float(v));
        };
        record_coords("lr_coords",coords); record_coords("hr_coords",plan.coords);
        debug["cascade"]={float(plan.actual_resolution),float(plan.budget_met)};
        for (const auto& a:plan.attempts) { debug["attempts"].push_back(float(a.resolution)); debug["attempts"].push_back(float(a.tokens)); }
        if (!flags["--dino"].empty()) {
            pixal::inspect_vision_checkpoint(flags.at("--dino")); pixal::inspect_vision_checkpoint(flags.at("--naf"));
            for (const auto* stage:{"--ss","--shape","--texture"}) pixal::inspect_flow_checkpoint(flags.at(stage));
            std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(gpu?ggml_backend_vk_init(std::stoi(flags.at("--device"))):ggml_backend_cpu_init(),ggml_backend_free);
            if (!backend) throw std::runtime_error("requested stage backend unavailable");
            if (!gpu) ggml_backend_cpu_set_n_threads(backend.get(),2);
            trellis::g_no_fa=true;
            pixal::VisionModel dino(flags.at("--dino"),backend.get()),naf(flags.at("--naf"),backend.get());
            pixal::FlowModel ss(flags.at("--ss"),backend.get()),shape(flags.at("--shape"),backend.get()),texture(flags.at("--texture"),backend.get());
            auto rgb=load("rgb"),target=load("target"),camera=load("camera");
            if (rgb.shape.size()!=3 || rgb.shape[0]!=3 || rgb.shape[1]!=rgb.shape[2] || rgb.shape[1]>64 || target.data.size()!=2 || camera.data.size()!=3)
                throw std::invalid_argument("invalid image fixture dimensions");
            auto features=pixal::encode_vision(dino,&naf,rgb.data,int(rgb.shape[1]),integer(target.data[0]),integer(target.data[1]),true);
            debug["global"]=features.dino.global; debug["patches"]=features.dino.patches.values; debug["high"]=features.high->values;
            pixal::Camera cam{camera.data[0],camera.data[1],camera.data[2],int(rgb.shape[1])};
            auto norm=[&](const std::string& name) {
                auto data=load(name);
                if (data.shape.size()!=2 || data.shape[0]!=2) throw std::invalid_argument("invalid normalization fixture");
                size_t half=data.data.size()/2;
                return pixal::LatentNormalization{{data.data.begin(),data.data.begin()+half},{data.data.begin()+half,data.data.end()}};
            };
            auto sn=norm("shape_norm"),tn=norm("texture_norm");
            if (fault=="zero_std") sn.std[0]=0;
            if (fault=="nan_norm") sn.mean[0]=std::numeric_limits<float>::quiet_NaN();
            if (fault=="norm_extent") sn.mean.pop_back();
            pixal::StageOptions options; options.f32_weight_arithmetic=true;
            options.sampler.steps=3; options.sampler.guidance_strength=2.5; options.sampler.guidance_rescale=.3; options.sampler.interval_start=0;
            int completed_steps=0;
            options.progress=[&](int done,int total) {
                if (done>0) ++completed_steps;
                debug["progress_events"].push_back(float(done)); debug["progress_events"].push_back(float(total));
            };
            options.cancelled=[&]() { return fault=="cancel_before_ss" || (fault=="cancel_between_stages" && completed_steps>=3); };
            std::vector<pixal::FlowStep> trace; options.trace=&trace;
            auto traces=[&](const std::string& label) { for (size_t i=0;i<trace.size();++i) debug[label+".sample"+std::to_string(i)]=trace[i].sample; trace.clear(); };
            auto dense=pixal::sample_structure_latent(fault=="wrong_stage"?shape:ss,features.dino,cam,load("ss_noise").data,options);
            debug["ss_dense"]=dense.values; traces("ss");
            if (fault=="coords_extent") coords[0][0]=integer(settings.data[1]);
            if (fault=="empty_coords") coords.clear();
            auto noise=load("lr_noise").data;
            if (fault=="noise_extent") noise.pop_back();
            if (fault=="nan_noise") noise[0]=std::numeric_limits<float>::quiet_NaN();
            auto lr=pixal::sample_shape_latent(shape,features.dino,&*features.high,cam,coords,integer(settings.data[1]),noise,sn,options);
            debug["lr"]=lr.values; traces("lr");
            // Fixture decoder coordinates stand in for shape_decoder.upsample(lr).
            // The real decoder must supply these before a full pipeline is adopted.
            auto hr=pixal::sample_shape_latent(shape,features.dino,&*features.high,cam,plan.coords,plan.actual_resolution/16,load("hr_noise").data,sn,options);
            debug["hr"]=hr.values; traces("hr"); debug["texture_concat"]=pixal::normalize_latent(hr.values,sn);
            if (fault=="texture_shape_extent") hr.values.pop_back();
            auto tex=pixal::sample_texture_latent(texture,features.dino,&*features.high,cam,hr,load("texture_noise").data,sn,tn,options);
            debug["texture"]=tex.values; traces("texture");
            if (tex.coords!=hr.coords || tex.grid_resolution!=hr.grid_resolution || completed_steps!=12)
                throw std::runtime_error("stage propagation or progress differs");
            debug["progress"]={float(completed_steps)};
            std::cout << "backend=" << ggml_backend_name(backend.get()) << " decoder_outputs=synthetic_fixtures steps=" << completed_steps << '\n';
        }
        for (const auto& [name,values]:debug) npy::save(directory+"/actual_"+name+".npy",values.data(),{int64_t(values.size())});
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
