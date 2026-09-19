// Test driver for trusted local synthetic fixtures; not a checkpoint loader.
#include "naf.h"
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
        if (argc<3) throw std::invalid_argument("usage: pixal-naf-check fixture cpu|vulkan [--device N] [--flow-gguf path] [--cancel-at N] [--f16-storage] [--projected-only] [--grid N]");
        std::string directory=argv[1],kind=argv[2],flow_path;
        int device=-1,cancel_at=0,checks=0,grid=4; bool half=false,projected_only=false;
        for (int i=3;i<argc;++i) {
            std::string flag=argv[i];
            if (flag=="--device" && i+1<argc) device=std::stoi(argv[++i]);
            else if (flag=="--flow-gguf" && i+1<argc) flow_path=argv[++i];
            else if (flag=="--cancel-at" && i+1<argc) cancel_at=std::stoi(argv[++i]);
            else if (flag=="--f16-storage") half=true;
            else if (flag=="--projected-only") projected_only=true;
            else if (flag=="--grid" && i+1<argc) grid=std::stoi(argv[++i]);
            else throw std::invalid_argument("invalid NAF checker argument");
        }
        if ((kind!="cpu" && kind!="vulkan") || (kind=="vulkan")!=(device>=0)) throw std::invalid_argument("explicit backend/device required");
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(
            kind=="cpu" ? ggml_backend_cpu_init() : ggml_backend_vk_init(device),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested NAF backend unavailable");
        if (kind=="cpu") ggml_backend_cpu_set_n_threads(backend.get(),2);
        pixal::NafParams p; int iw=0,ih=0,ow=0,oh=0;
        std::ifstream config(directory+"/params.txt");
        config >> p.channels >> p.heads >> p.rope_heads >> p.layers >> p.kernel >> p.tile_pixels >> iw >> ih >> ow >> oh;
        if (!config || p.channels>256 || p.layers>2 || iw>128 || ih>128 || ow>(projected_only ? 1024 : 64) || oh>(projected_only ? 1024 : 64))
            throw std::invalid_argument("invalid synthetic NAF dimensions");
        p.f32_weight_arithmetic=true;
        auto load=[&](const std::string& name) {
            auto a=npy::load(directory+"/"+name+".npy");
            if (a.numel()>8000000) throw std::invalid_argument("synthetic NAF tensor too large");
            return a;
        };
        trellis::Model model; model.backend=backend.get();
        std::unique_ptr<ggml_context,decltype(&ggml_free)> ctx(ggml_init({ggml_tensor_overhead()*1024,nullptr,true}),ggml_free);
        std::map<ggml_tensor*,std::vector<float>> values;
        std::ifstream weights(directory+"/weights.txt"); std::string name;
        while (std::getline(weights,name)) {
            if (name.empty() || name.find("..")!=std::string::npos || name.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789._")!=std::string::npos)
                throw std::invalid_argument("invalid synthetic NAF weight name");
            auto a=load("weights/"+name);
            if (a.shape.empty() || a.shape.size()>4) throw std::invalid_argument("invalid NAF fixture rank");
            std::vector<int64_t> dims(a.shape.rbegin(),a.shape.rend());
            auto* t=ggml_new_tensor(ctx.get(),half ? GGML_TYPE_F16 : GGML_TYPE_F32,dims.size(),dims.data());
            model.tensors[name]=t; values[t]=std::move(a.data);
        }
        std::unique_ptr<ggml_backend_buffer,decltype(&ggml_backend_buffer_free)> buffer(
            ggml_backend_alloc_ctx_tensors(ctx.get(),backend.get()),ggml_backend_buffer_free);
        if (!buffer) throw std::runtime_error("cannot allocate synthetic NAF weights");
        for (const auto& [t,v]:values) {
            if (half) {
                std::vector<ggml_fp16_t> fp16(v.size()); ggml_fp32_to_fp16_row(v.data(),fp16.data(),v.size());
                ggml_backend_tensor_set(t,fp16.data(),0,fp16.size()*sizeof(ggml_fp16_t));
            } else ggml_backend_tensor_set(t,v.data(),0,v.size()*sizeof(float));
        }
        auto low=load("low");
        if (low.shape.size()!=3) throw std::invalid_argument("invalid low-resolution fixture rank");
        pixal::FeatureMap fmap{int(low.shape[2]),int(low.shape[1]),int(low.shape[0]),low.data};
        std::map<std::string,std::vector<float>> debug; pixal::NafStats stats;
        auto cancelled=[&]() { ++checks; return cancel_at>0 && checks>=cancel_at; };
        auto array=load("coordinates");
        if (array.shape.size()!=2 || array.shape[1]!=3) throw std::invalid_argument("invalid test coordinates");
        std::vector<std::array<int,3>> coords;
        for (size_t i=0;i<array.data.size();i+=3) coords.push_back({int(array.data[i]),int(array.data[i+1]),int(array.data[i+2])});
        auto rgb=load("rgb").data;
        pixal::NafStats repeated_stats,projected_stats;
        const pixal::Camera camera{.857556f,2.f,1.f,iw};
        if (projected_only) {
            auto value=pixal::project_naf(model,p,rgb,iw,ih,fmap,ow,oh,coords,grid,camera,&projected_stats,nullptr,cancelled);
            npy::save(directory+"/actual_sparse.npy",value.data(),{int64_t(value.size())});
            std::ofstream info(directory+"/stats.json");
            info << "{\"encoder_graph_bytes\":" << projected_stats.encoder_graph_bytes
                 << ",\"attention_graph_bytes\":" << projected_stats.attention_graph_bytes
                 << ",\"tiles\":" << projected_stats.tiles << ",\"output_bytes\":" << projected_stats.output_bytes
                 << ",\"dense_output_bytes\":" << projected_stats.dense_output_bytes
                 << ",\"attention_queries\":" << projected_stats.attention_queries << "}\n";
            return 0;
        }
        auto high=pixal::upsample_naf(model,p,rgb,iw,ih,fmap,ow,oh,&stats,&debug,cancelled);
        debug["high"]=high.values;
        auto repeated=pixal::upsample_naf(model,p,rgb,iw,ih,fmap,ow,oh,&repeated_stats);
        if (high.values!=repeated.values) throw std::runtime_error("dense NAF output changed without debug graph");
        const std::vector<pixal::Camera> cameras{camera,{.1f,.2f,1.f,iw},{1.7f,.1f,.3f,iw}};
        std::vector<float> sparse;
        for (size_t i=0;i<cameras.size();++i) {
            auto value=pixal::project_naf(model,p,rgb,iw,ih,fmap,ow,oh,coords,grid,cameras[i],&projected_stats);
            debug["sparse"+std::to_string(i)]=value;
            pixal::ImageFeatures features{std::vector<float>(5*fmap.channels,0.f),fmap};
            auto full=pixal::image_conditions(backend.get(),features,coords,grid,cameras[i],&high);
            auto reduced=pixal::image_conditions_projected(backend.get(),features,coords,grid,cameras[i],value);
            if (full.positive.projected!=reduced.positive.projected || full.negative.projected!=reduced.negative.projected)
                throw std::runtime_error("projected NAF differs from native dense NAF projection");
            if (i==0) sparse=value;
        }
        auto other=p;other.tile_pixels=p.tile_pixels==128 ? 7 : 128;
        if (sparse!=pixal::project_naf(model,other,rgb,iw,ih,fmap,ow,oh,coords,grid,camera))
            throw std::runtime_error("projected NAF changed with tile size");
        if (!flow_path.empty()) {
            pixal::ImageFeatures features{load("global").data,fmap};
            auto pair=pixal::image_conditions_projected(backend.get(),features,coords,grid,camera,sparse);
            debug["projected"]=pair.positive.projected;
            pixal::FlowModel flow(flow_path,backend.get()); trellis::g_no_fa=true;
            pixal::FlowRunner runner(flow,coords,features.global.size()/fmap.channels,true);
            pixal::FlowSamplerParams params; params.steps=3; params.guidance_strength=2.5; params.guidance_rescale=.3; params.interval_start=0;
            auto forward=[&](const std::vector<float>& x,float t,const pixal::FlowCondition& condition) { return runner.forward(x,t,condition); };
            std::vector<pixal::FlowStep> trace;
            pixal::sample_flow(forward,load("noise").data,pair.positive,pair.negative,params,true,flow.spec().params.out_ch,&trace);
            for (size_t i=0;i<trace.size();++i) debug["sample"+std::to_string(i)]=trace[i].sample;
        }
        for (const auto& [label,v]:debug) npy::save(directory+"/actual_"+label+".npy",v.data(),{int64_t(v.size())});
        std::ofstream info(directory+"/stats.json");
        info << "{\"encoder_graph_bytes\":" << repeated_stats.encoder_graph_bytes << ",\"attention_graph_bytes\":" << repeated_stats.attention_graph_bytes
             << ",\"tiles\":" << stats.tiles << ",\"guide_width\":" << stats.guide_width << ",\"guide_height\":" << stats.guide_height
             << ",\"projected_output_bytes\":" << projected_stats.output_bytes
             << ",\"dense_output_bytes\":" << projected_stats.dense_output_bytes
             << ",\"projected_attention_queries\":" << projected_stats.attention_queries
             << ",\"projected_tiles\":" << projected_stats.tiles
             << ",\"projected_dense_bitwise_equal\":true,\"projected_retile_bitwise_equal\":true"
             << ",\"repeat_bitwise_equal\":true,\"cancel_checks\":" << checks << "}\n";
        std::cout << "backend=" << ggml_backend_name(backend.get()) << " tiles=" << stats.tiles << '\n';
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
