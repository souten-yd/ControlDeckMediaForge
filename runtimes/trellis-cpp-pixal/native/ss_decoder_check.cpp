#include "ss_decoder.h"
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
        if (argc==3 && std::string(argv[1])=="--inspect") {
            auto spec=pixal::inspect_ss_decoder_checkpoint(argv[2]);
            std::cout << "metadata_verified stages=" << spec.params.channels.size() << '\n'; return 0;
        }
        if (argc<4) throw std::invalid_argument("usage: pixal-ss-decoder-check fixture cpu|vulkan decoder.gguf [--device N] [--flow path --dino path --naf path --shape path] [--fault name]");
        std::string directory=argv[1],kind=argv[2],checkpoint=argv[3]; std::map<std::string,std::string> flags;
        for (int i=4;i<argc;++i) {
            std::string flag=argv[i];
            if (i+1>=argc || (flag!="--device" && flag!="--flow" && flag!="--dino" && flag!="--naf" && flag!="--shape" && flag!="--fault"))
                throw std::invalid_argument("invalid SS decoder checker argument");
            flags[flag]=argv[++i];
        }
        bool gpu=kind=="vulkan";
        if ((kind!="cpu" && !gpu) || gpu!=(flags.count("--device")!=0)) throw std::invalid_argument("explicit SS decoder backend/device required");
        pixal::inspect_ss_decoder_checkpoint(checkpoint);
        for (const auto& flag:{"--flow","--shape"}) if (flags.count(flag)) pixal::inspect_flow_checkpoint(flags.at(flag));
        for (const auto& flag:{"--dino","--naf"}) if (flags.count(flag)) pixal::inspect_vision_checkpoint(flags.at(flag));
        std::cout << "metadata_verified\n";
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(gpu?ggml_backend_vk_init(std::stoi(flags.at("--device"))):ggml_backend_cpu_init(),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested SS decoder backend unavailable");
        if (!gpu) ggml_backend_cpu_set_n_threads(backend.get(),2);
        std::cout << "backend_initialized=" << ggml_backend_name(backend.get()) << '\n';
        auto load=[&](const std::string& name) { auto a=npy::load(directory+"/"+name+".npy"); if (a.numel()>4000000) throw std::invalid_argument("SS decoder fixture too large"); return a; };
        auto input=load("latent"),requested=load("output_resolution");
        if (input.shape.size()!=4 || input.shape[1]!=input.shape[2] || input.shape[2]!=input.shape[3] || requested.data.size()!=1 || !std::isfinite(requested.data[0]) || requested.data[0]!=std::floor(requested.data[0]) || requested.data[0]<2 || requested.data[0]>256)
            throw std::invalid_argument("invalid SS decoder fixture dimensions");
        const int output_resolution=int(requested.data[0]);
        std::map<std::string,std::vector<float>> debug;
        {
            pixal::SsDecoderModel model(checkpoint,backend.get());
            pixal::DenseLatent latent{int(input.shape[1]),int(input.shape[0]),input.data};
            pixal::SsDecoderOptions options; const auto fault=flags["--fault"];
            options.f32_arithmetic=fault!="reference_precision";
            int finished=0;
            options.progress=[&](int done,int total) { finished=done; debug["progress"].push_back(float(done)); debug["progress"].push_back(float(total)); };
            options.cancelled=[&]() { return fault=="cancel_before" || (fault=="cancel_between" && finished>0) || (fault=="cancel_final" && finished==int(model.spec().params.channels.size())); };
            if (fault=="nan_latent") latent.values[0]=std::numeric_limits<float>::quiet_NaN();
            if (fault=="latent_extent") latent.values.pop_back();
            if (fault=="latent_channels") ++latent.channels;
            if (fault=="latent_resolution") latent.resolution=std::numeric_limits<int>::max();
            pixal::SsDecoderStats stats;
            std::map<std::string,std::vector<float>> intermediates;
            pixal::Coordinates coords;
            if (!flags["--flow"].empty()) {
                pixal::VisionModel dino(flags.at("--dino"),backend.get()),naf(flags.at("--naf"),backend.get());
                pixal::FlowModel flow(flags.at("--flow"),backend.get()),shape(flags.at("--shape"),backend.get());
                auto rgb=load("rgb"),camera=load("camera");
                if (rgb.shape.size()!=3 || rgb.shape[0]!=3 || rgb.shape[1]!=rgb.shape[2] || rgb.shape[1]>64 || camera.data.size()!=3)
                    throw std::invalid_argument("invalid connected SS image fixture");
                auto features=pixal::encode_vision(dino,&naf,rgb.data,int(rgb.shape[1]),8,8,true);
                pixal::Camera cam{camera.data[0],camera.data[1],camera.data[2],int(rgb.shape[1])};
                trellis::g_no_fa=true;
                pixal::StageOptions stage; stage.f32_weight_arithmetic=true; stage.sampler.steps=3;
                stage.sampler.guidance_strength=2.5; stage.sampler.guidance_rescale=.3; stage.sampler.interval_start=0;
                stage.cancelled=[&]() { return fault=="wrapper_cancel" && finished>0; };
                std::vector<pixal::FlowStep> trace; stage.trace=&trace;
                coords=pixal::sample_sparse_structure(fault=="flow_mismatch"?shape:flow,model,features.dino,cam,load("noise").data,
                    fault=="wrapper_bad_pool"?3:output_resolution,stage,options,&stats,&intermediates);
                for (size_t i=0;i<trace.size();++i) debug["ss.sample"+std::to_string(i)]=trace[i].sample;
                pixal::LatentNormalization n{{-.7f,-.4f,-.1f,.2f,.5f,.8f,1.1f,1.4f},{.2f,.4f,.6f,.8f,1.f,1.2f,1.4f,1.6f}};
                trace.clear();
                auto slat=pixal::sample_shape_latent(shape,features.dino,&*features.high,cam,coords,output_resolution,load("shape_noise").data,n,stage);
                debug["shape"]=slat.values;
                for (size_t i=0;i<trace.size();++i) debug["shape.sample"+std::to_string(i)]=trace[i].sample;
            } else {
                auto occupancy=pixal::decode_structure(model,latent,options,&stats,&intermediates);
                debug["logits"]=occupancy.logits;
                coords=pixal::occupancy_coordinates(occupancy.logits,occupancy.resolution,output_resolution);
                auto repeated=pixal::decode_structure(model,latent,{true,{},{}});
                if (occupancy.logits!=repeated.logits) throw std::runtime_error("SS decoder debug/no-debug outputs differ");
            }
            for (auto& [name,value]:intermediates) debug[name]=std::move(value);
            debug["coords"]={};
            for (const auto& coord:coords) for (int v:coord) debug["coords"].push_back(float(v));
            for (const auto& [name,t]:model.weights().tensors) debug["weight."+name]=trellis::tensor_to_f32(t);
            std::cout << "segment_graph_bytes=";
            for (auto bytes:stats.segment_graph_bytes) std::cout << bytes << ',';
            std::cout << " coordinates=" << coords.size() << '\n';
        }
        if (std::string(ggml_backend_name(backend.get())).empty()) throw std::runtime_error("borrowed SS decoder backend lost");
        for (const auto& [name,value]:debug) npy::save(directory+"/actual_"+name+".npy",value.data(),{int64_t(value.size())});
        std::cout << "borrowed_backend_retained=true\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
