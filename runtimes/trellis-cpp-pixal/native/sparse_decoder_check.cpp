#include "sparse_decoder.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace pixal=mediaforge::pixal;
int main(int argc,char** argv) {
    try {
        if (argc==3 && std::string(argv[1])=="--inspect") {
            auto s=pixal::inspect_sparse_decoder_checkpoint(argv[2]);
            std::cout << "metadata_verified kind=" << s.params.kind << " stages=" << s.params.channels.size() << '\n'; return 0;
        }
        if (argc<5) throw std::invalid_argument("usage: pixal-sparse-decoder-check fixture cpu|vulkan shape.gguf texture.gguf [--device N] [--fault name] [--chunk N]");
        const std::string directory=argv[1],kind=argv[2],shape_path=argv[3],texture_path=argv[4];
        std::map<std::string,std::string> flags;
        for (int i=5;i<argc;++i) {
            std::string flag=argv[i];
            if (i+1>=argc || (flag!="--device" && flag!="--fault" && flag!="--chunk") || flags.count(flag)) throw std::invalid_argument("invalid sparse checker argument");
            flags[flag]=argv[++i];
        }
        bool gpu=kind=="vulkan";
        if ((kind!="cpu" && !gpu) || gpu!=(flags.count("--device")!=0)) throw std::invalid_argument("explicit sparse backend/device required");
        pixal::inspect_sparse_decoder_checkpoint(shape_path); pixal::inspect_sparse_decoder_checkpoint(texture_path);
        std::cout << "metadata_verified\n";
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(gpu?ggml_backend_vk_init(std::stoi(flags.at("--device"))):ggml_backend_cpu_init(),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested sparse backend unavailable");
        if (!gpu) ggml_backend_cpu_set_n_threads(backend.get(),2);
        std::cout << "backend_initialized=" << ggml_backend_name(backend.get()) << '\n';
        auto load=[&](const std::string& name) { auto a=npy::load(directory+"/"+name+".npy"); if (a.numel()>4000000) throw std::invalid_argument("sparse fixture too large"); return a; };
        auto coords=load("coords"),settings=load("settings"),shape=load("shape"),texture=load("texture");
        if (coords.shape.size()!=2 || coords.shape[1]!=3 || shape.shape.size()!=2 || texture.shape.size()!=2 ||
            shape.shape!=texture.shape || coords.shape[0]!=shape.shape[0] || settings.data.size()!=1 ||
            !std::isfinite(settings.data[0]) || settings.data[0]!=std::floor(settings.data[0]) || settings.data[0]<2 || settings.data[0]>4096)
            throw std::invalid_argument("invalid sparse fixture dimensions");
        pixal::SparseLatent input; input.grid_resolution=int(settings.data[0]); input.channels=int(shape.shape[1]); input.values=shape.data;
        for (size_t i=0;i<coords.data.size();i+=3) {
            std::array<int,3> c;
            for (int j=0;j<3;++j) {
                auto v=coords.data[i+j];
                if (!std::isfinite(v) || v!=std::floor(v) || v<0 || v>=input.grid_resolution) throw std::invalid_argument("invalid fixture coordinate");
                c[j]=int(v);
            }
            input.coords.push_back(c);
        }
        std::map<std::string,std::vector<float>> debug;
        auto save_coords=[&](const std::string& label,const pixal::Coordinates& cs) { for (const auto& c:cs) for (int v:c) debug[label].push_back(float(v)); };
        {
            pixal::SparseDecoderModel sm(shape_path,backend.get()),tm(texture_path,backend.get());
            const auto fault=flags["--fault"];
            pixal::SparseDecoderOptions options; options.f32_arithmetic=fault!="reference_precision";
            options.chunk_rows=flags.count("--chunk")?std::stoi(flags.at("--chunk")):7;
            int finished=0;
            options.progress=[&](int done,int total) { finished=done; debug["shape.progress"].push_back(float(done)); debug["shape.progress"].push_back(float(total)); };
            options.cancelled=[&]() { return fault=="cancel_before" || (fault=="cancel_between" && finished>0) || (fault=="cancel_final" && finished==int(sm.spec().params.channels.size())); };
            if (fault=="nan_latent") input.values[0]=std::numeric_limits<float>::quiet_NaN();
            if (fault=="extent") input.values.pop_back();
            if (fault=="channels") ++input.channels;
            if (fault=="coordinate") input.coords[0][0]=-1;
            if (fault=="duplicate") input.coords[0]=input.coords.back();
            if (fault=="grid") input.grid_resolution=4096;
            if (fault=="chunk") options.chunk_rows=0;
            if (fault=="budget") options.max_voxels=input.coords.size();
            pixal::SparseDecoderStats ss,ts;
            std::map<std::string,std::vector<float>> observed;
            auto s=pixal::decode_sparse(fault=="model_kind"?tm:sm,input,nullptr,options,&ss,&observed);
            for (auto& [name,value]:observed) debug["shape."+name]=std::move(value);
            save_coords("shape.coords",s.fields.coords);
            for (size_t i=0;i<s.subdivisions.size();++i) save_coords("shape.guide"+std::to_string(i)+".coords",s.subdivisions[i].coords);
            options.progress={}; options.cancelled={};
            if (fault=="guide_missing") s.subdivisions.clear();
            if (fault=="guide_order") std::swap(s.subdivisions[0].coords.front(),s.subdivisions[0].coords.back());
            if (fault=="guide_grid") ++s.subdivisions[0].grid_resolution;
            if (fault=="guide_extent") s.subdivisions[0].logits.pop_back();
            if (fault=="guide_nan") s.subdivisions[0].logits[0]=std::numeric_limits<float>::quiet_NaN();
            if (fault=="guide_empty") std::fill(s.subdivisions[0].logits.begin(),s.subdivisions[0].logits.end(),0.f);
            input.values=texture.data;
            auto t=pixal::decode_sparse(tm,input,&s.subdivisions,options,&ts,&observed);
            if (s.fields.coords!=t.fields.coords || s.fields.grid_resolution!=t.fields.grid_resolution) throw std::runtime_error("shape/texture output coordinates differ");
            for (auto& [name,value]:observed) debug["texture."+name]=std::move(value);
            save_coords("texture.coords",t.fields.coords);
            debug["output_grid"]={float(s.fields.grid_resolution)};
            input.values=shape.data;
            for (int i=0;i<int(sm.spec().params.channels.size());++i) save_coords("upsample"+std::to_string(i),pixal::upsample_shape(sm,input,fault=="upsample_count"?99:i,options));
            options.chunk_rows=options.chunk_rows==19?3:19;
            auto repeated=pixal::decode_sparse(sm,input,nullptr,options);
            if (s.fields.coords!=repeated.fields.coords) throw std::runtime_error("chunk size changed subdivision");
            debug["shape.repeated"]=repeated.fields.values;
            input.values=texture.data;
            debug["texture.repeated"]=pixal::decode_sparse(tm,input,&repeated.subdivisions,options).fields.values;
            for (const auto& [label,model]:std::vector<std::pair<std::string,const pixal::SparseDecoderModel*>>{{"shape",&sm},{"texture",&tm}})
                for (const auto& [name,tensor]:model->weights().tensors) debug[label+".weight."+name]=trellis::tensor_to_f32(tensor);
            std::cout << "shape_graph_peak_bytes=" << ss.graph_peak_bytes << " texture_graph_peak_bytes=" << ts.graph_peak_bytes
                << " shape_input_buffer_max_bytes=" << ss.input_buffer_max_bytes << " texture_input_buffer_max_bytes=" << ts.input_buffer_max_bytes
                << " graphs=" << ss.graph_executions+ts.graph_executions << " output_voxels=" << s.fields.coords.size() << '\n';
        }
        if (std::string(ggml_backend_name(backend.get())).empty()) throw std::runtime_error("borrowed sparse backend lost");
        for (const auto& [name,value]:debug) npy::save(directory+"/actual_"+name+".npy",value.data(),{int64_t(value.size())});
        std::cout << "borrowed_backend_retained=true\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
