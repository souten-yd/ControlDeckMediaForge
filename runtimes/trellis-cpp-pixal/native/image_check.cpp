// Locally generated synthetic fixtures, never arbitrary uploaded model files.
#include "image_features.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace pixal=mediaforge::pixal;
namespace trellis { extern bool g_no_fa; }
int main(int argc,char** argv) {
    try {
        if (argc<3) throw std::invalid_argument("usage: pixal-image-check <fixture> cpu|vulkan [--device N] [--flow-gguf path]");
        std::string directory=argv[1],kind=argv[2],flow_path;
        int device=-1; bool with_high=false;
        for (int i=3;i<argc;++i) {
            const std::string flag=argv[i];
            if (flag=="--device" && i+1<argc) device=std::stoi(argv[++i]);
            else if (flag=="--flow-gguf" && i+1<argc) flow_path=argv[++i];
            else if (flag=="--with-high") with_high=true;
            else throw std::invalid_argument("invalid image checker argument");
        }
        if ((kind!="cpu" && kind!="vulkan") || (kind=="vulkan")!=(device>=0)) throw std::invalid_argument("explicit backend/device required");
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(
            kind=="cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(device),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested image backend unavailable");
        if (kind=="cpu") ggml_backend_cpu_set_n_threads(backend.get(),2);
        pixal::DinoParams p;
        int image_size=0;
        std::ifstream config(directory+"/params.txt");
        config >> p.channels >> p.heads >> p.layers >> p.patch_size >> p.registers >> p.mlp_channels >> image_size;
        if (!config || p.channels>128 || p.layers>4 || image_size>64) throw std::invalid_argument("synthetic DINO dimensions too large");
        p.f32_weight_arithmetic=true;
        auto load=[&](const std::string& name) {
            auto a=npy::load(directory+"/"+name+".npy");
            if (a.numel()>4000000) throw std::invalid_argument("synthetic image tensor too large");
            return a;
        };
        trellis::Model model; model.backend=backend.get();
        std::unique_ptr<ggml_context,decltype(&ggml_free)> ctx(ggml_init({ggml_tensor_overhead()*1024,nullptr,true}),ggml_free);
        std::map<ggml_tensor*,std::vector<float>> values;
        std::ifstream weights(directory+"/weights.txt");
        std::string name;
        while (std::getline(weights,name)) {
            if (name.empty() || name.find("..")!=std::string::npos || name.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789._")!=std::string::npos)
                throw std::invalid_argument("invalid synthetic DINO weight name");
            auto a=load("weights/"+name);
            if (a.shape.empty() || a.shape.size()>4) throw std::invalid_argument("invalid DINO fixture rank");
            std::vector<int64_t> dims(a.shape.rbegin(),a.shape.rend());
            auto* t=ggml_new_tensor(ctx.get(),GGML_TYPE_F32,dims.size(),dims.data());
            model.tensors[name]=t; values[t]=std::move(a.data);
        }
        std::unique_ptr<ggml_backend_buffer,decltype(&ggml_backend_buffer_free)> buffer(
            ggml_backend_alloc_ctx_tensors(ctx.get(),backend.get()),ggml_backend_buffer_free);
        if (!buffer) throw std::runtime_error("cannot allocate synthetic DINO weights");
        for (const auto& [t,v]:values) ggml_backend_tensor_set(t,v.data(),0,v.size()*sizeof(float));
        std::map<std::string,std::vector<float>> debug;
        auto rgb=load("rgb");
        auto features=pixal::encode_dino(model,p,rgb.data,image_size,&debug);
        debug["global"]=features.global; debug["patches"]=features.patches.values;
        auto array=load("coordinates");
        if (array.shape.size()!=2 || array.shape[1]!=3) throw std::invalid_argument("invalid image test coordinates");
        std::vector<std::array<int,3>> coords;
        for (size_t i=0;i<array.data.size();i+=3) coords.push_back({int(array.data[i]),int(array.data[i+1]),int(array.data[i+2])});
        auto camera=load("camera");
        if (camera.data.size()!=4) throw std::invalid_argument("invalid test camera");
        pixal::FeatureMap high;
        if (with_high) {
            auto data=load("high");
            if (data.shape.size()!=3) throw std::invalid_argument("invalid high feature fixture");
            high={int(data.shape[2]),int(data.shape[1]),int(data.shape[0]),std::move(data.data)};
        }
        auto pair=pixal::image_conditions(backend.get(),features,coords,int(camera.data[3]),
            {camera.data[0],camera.data[1],camera.data[2],image_size},with_high ? &high : nullptr);
        debug["projected"]=pair.positive.projected;
        debug["negative_global"]=pair.negative.global; debug["negative_projected"]=pair.negative.projected;
        if (!flow_path.empty()) {
            pixal::FlowModel flow(flow_path,backend.get());
            trellis::g_no_fa=true;
            pixal::FlowRunner runner(flow,coords,1+p.registers,true);
            const auto noise=load("noise").data;
            pixal::FlowSamplerParams params;
            params.steps=3; params.guidance_strength=2.5; params.guidance_rescale=.3; params.interval_start=0;
            auto forward=[&](const std::vector<float>& x,float t,const pixal::FlowCondition& condition) { return runner.forward(x,t,condition); };
            std::vector<pixal::FlowStep> trace;
            pixal::sample_flow(forward,noise,pair.positive,pair.negative,params,flow.spec().stage!="ss",flow.spec().params.out_ch,&trace);
            for (size_t i=0;i<trace.size();++i) debug["sample"+std::to_string(i)]=trace[i].sample;
        }
        for (const auto& [label,v]:debug) npy::save(directory+"/actual_"+label+".npy",v.data(),{(int64_t)v.size()});
        std::cout << "backend=" << ggml_backend_name(backend.get()) << " DINO_channels=" << p.channels << '\n';
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
