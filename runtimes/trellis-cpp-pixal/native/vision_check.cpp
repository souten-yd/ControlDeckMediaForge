// Trusted local fixtures only. Model parameters come from converted GGUF.
#include "vision_checkpoint.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <iostream>
#include <stdexcept>

namespace pixal=mediaforge::pixal;
namespace trellis { extern bool g_no_fa; }
int main(int argc,char** argv) {
    try {
        if (argc==3 && std::string(argv[1])=="--inspect") {
            auto spec=pixal::inspect_vision_checkpoint(argv[2]);
            std::cout << "metadata_verified kind=" << spec.kind << " storage=" << spec.storage << '\n'; return 0;
        }
        if (argc<3) throw std::invalid_argument("usage: pixal-vision-check fixture cpu|vulkan --dino path [--naf path] [--flow path] [--device N] [--cancel-at N]");
        std::string directory=argv[1],kind=argv[2],dino_path,naf_path,flow_path;
        int device=-1,cancel_at=0,checks=0;
        for (int i=3;i<argc;++i) {
            std::string flag=argv[i];
            if (i+1>=argc) throw std::invalid_argument("missing vision checker argument");
            if (flag=="--device") device=std::stoi(argv[++i]);
            else if (flag=="--dino") dino_path=argv[++i];
            else if (flag=="--naf") naf_path=argv[++i];
            else if (flag=="--flow") flow_path=argv[++i];
            else if (flag=="--cancel-at") cancel_at=std::stoi(argv[++i]);
            else throw std::invalid_argument("unknown vision checker argument");
        }
        if ((kind!="cpu" && kind!="vulkan") || (kind=="vulkan")!=(device>=0)) throw std::invalid_argument("explicit vision backend/device required");
        auto ds=pixal::inspect_vision_checkpoint(dino_path);
        if (ds.kind!="dino") throw std::invalid_argument("DINO path has wrong component kind");
        if (!naf_path.empty() && pixal::inspect_vision_checkpoint(naf_path).kind!="naf") throw std::invalid_argument("NAF path has wrong component kind");
        if (!flow_path.empty()) pixal::inspect_flow_checkpoint(flow_path);
        std::cout << "metadata_verified\n";
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(
            kind=="cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(device),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested vision backend unavailable");
        std::cout << "backend_initialized=" << ggml_backend_name(backend.get()) << '\n';
        if (kind=="cpu") ggml_backend_cpu_set_n_threads(backend.get(),2);
        std::map<std::string,std::vector<float>> debug;
        {
            pixal::VisionModel dino(dino_path,backend.get());
            std::unique_ptr<pixal::VisionModel> naf;
            if (!naf_path.empty()) naf=std::make_unique<pixal::VisionModel>(naf_path,backend.get());
            auto load=[&](const std::string& name) {
                auto a=npy::load(directory+"/"+name+".npy");
                if (a.numel()>4000000) throw std::invalid_argument("synthetic vision fixture too large");
                return a;
            };
            auto rgb=load("rgb"),target=load("target");
            if (rgb.shape.size()!=3 || rgb.shape[0]!=3 || rgb.shape[1]!=rgb.shape[2] || rgb.shape[1]>64 || target.data.size()!=2)
                throw std::invalid_argument("invalid vision fixture RGB/target");
            auto cancelled=[&]() { return cancel_at>0 && ++checks>=cancel_at; };
            pixal::NafStats stats;
            auto features=pixal::encode_vision(dino,naf.get(),rgb.data,rgb.shape[1],int(target.data[0]),int(target.data[1]),true,&stats,&debug,cancelled);
            debug["global"]=features.dino.global; debug["patches"]=features.dino.patches.values;
            if (features.high) debug["high"]=features.high->values;
            auto repeated=pixal::encode_vision(dino,naf.get(),rgb.data,rgb.shape[1],int(target.data[0]),int(target.data[1]),true);
            if (features.dino.global!=repeated.dino.global || features.dino.patches.values!=repeated.dino.patches.values ||
                (features.high && features.high->values!=repeated.high->values)) throw std::runtime_error("vision repeat differs without diagnostic outputs");
            auto camera=load("camera"),coordinates=load("coordinates");
            if (camera.data.size()!=4 || coordinates.shape.size()!=2 || coordinates.shape[1]!=3) throw std::invalid_argument("invalid vision fixture camera/coordinates");
            std::vector<std::array<int,3>> coords;
            for (size_t i=0;i<coordinates.data.size();i+=3) coords.push_back({int(coordinates.data[i]),int(coordinates.data[i+1]),int(coordinates.data[i+2])});
            auto pair=pixal::image_conditions(backend.get(),features.dino,coords,int(camera.data[3]),
                       {camera.data[0],camera.data[1],camera.data[2],int(rgb.shape[1])},features.high ? &*features.high : nullptr);
            debug["projected"]=pair.positive.projected; debug["negative_projected"]=pair.negative.projected;
            if (!flow_path.empty()) {
                pixal::FlowModel flow(flow_path,backend.get()); trellis::g_no_fa=true;
                pixal::FlowRunner runner(flow,coords,features.dino.global.size()/features.dino.patches.channels,true);
                pixal::FlowSamplerParams params; params.steps=3; params.guidance_strength=2.5; params.guidance_rescale=.3; params.interval_start=0;
                auto forward=[&](const std::vector<float>& x,float t,const pixal::FlowCondition& condition) { return runner.forward(x,t,condition); };
                std::vector<pixal::FlowStep> trace;
                pixal::sample_flow(forward,load("noise").data,pair.positive,pair.negative,params,flow.spec().stage!="ss",flow.spec().params.out_ch,&trace);
                for (size_t i=0;i<trace.size();++i) debug["sample"+std::to_string(i)]=trace[i].sample;
            }
            for (const auto& [name,t]:dino.weights().tensors) debug["weight.dino."+name]=trellis::tensor_to_f32(t);
            if (naf) for (const auto& [name,t]:naf->weights().tensors) debug["weight.naf."+name]=trellis::tensor_to_f32(t);
        }
        // Borrowed backend must still be usable after both models are destroyed.
        if (std::string(ggml_backend_name(backend.get())).empty()) throw std::runtime_error("borrowed vision backend was lost");
        for (const auto& [name,values]:debug) npy::save(directory+"/actual_"+name+".npy",values.data(),{int64_t(values.size())});
        std::cout << "repeat_bitwise_equal=true borrowed_backend_retained=true\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
