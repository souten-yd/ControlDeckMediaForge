#include "mesh_decode.h"
#include "dual_grid.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace pixal=mediaforge::pixal;
int main(int argc,char** argv) {
    try {
        if (argc<2) throw std::invalid_argument("usage: pixal-mesh-check fixture [--shape path --texture path --backend cpu|vulkan --device N] [--fault name]");
        std::string directory=argv[1]; std::map<std::string,std::string> flags;
        for (int i=2;i<argc;++i) {
            std::string name=argv[i];
            if (i+1>=argc || (name!="--shape" && name!="--texture" && name!="--backend" && name!="--device" && name!="--fault") || flags.count(name)) throw std::invalid_argument("invalid mesh check argument");
            flags[name]=argv[++i];
        }
        const auto fault=flags["--fault"];
        auto load=[&](const std::string& name) { auto x=npy::load(directory+"/"+name+".npy"); if (x.numel()>4000000) throw std::invalid_argument("mesh fixture too large"); return x; };
        auto cs=load("coords"),settings=load("settings"),sf=load("shape"),tf=load("texture");
        if (settings.data.size()!=3 || cs.shape.size()!=2 || cs.shape[1]!=3 || sf.shape.size()!=2 || tf.shape.size()!=2 ||
            sf.shape[0]!=cs.shape[0] || tf.shape[0]!=cs.shape[0] || !std::isfinite(settings.data[0]) || settings.data[0]!=std::floor(settings.data[0]) ||
            settings.data[0]<2 || settings.data[0]>4096 || (settings.data[2]!=0 && settings.data[2]!=1)) throw std::invalid_argument("invalid mesh fixture dimensions");
        pixal::SparseLatent shape,texture;
        shape.grid_resolution=int(settings.data[0]); shape.channels=int(sf.shape[1]); shape.values=sf.data;
        for (size_t i=0;i<cs.data.size();i+=3) {
            std::array<int,3> c;
            for (int j=0;j<3;++j) {
                float v=cs.data[i+j]; if (!std::isfinite(v) || v!=std::floor(v) || v<0 || v>=shape.grid_resolution) throw std::invalid_argument("invalid mesh fixture coordinate"); c[j]=int(v);
            }
            shape.coords.push_back(c);
        }
        texture=shape; texture.channels=int(tf.shape[1]); texture.values=tf.data;
        pixal::MeshDecodeOptions options; options.require_faces=settings.data[2]!=0;
        int mesh_progress=-1,decoder_completions=0;
        std::map<std::string,std::vector<float>> debug;
        options.progress=[&](int done,int total) { mesh_progress=done; debug["progress"].push_back(float(done)); debug["progress"].push_back(float(total)); };
        options.cancelled=[&]() { return fault=="cancel_before" || (fault=="cancel_vertices" && mesh_progress==1) || (fault=="cancel_final" && mesh_progress==2); };
        float margin=settings.data[1];
        if (fault=="nan") shape.values[0]=std::numeric_limits<float>::quiet_NaN();
        if (fault=="extent") shape.values.pop_back();
        if (fault=="channels") ++shape.channels;
        if (fault=="coordinate") shape.coords[0][0]=-1;
        if (fault=="duplicate") shape.coords[0]=shape.coords.back();
        if (fault=="grid") shape.grid_resolution=0;
        if (fault=="margin") margin=std::numeric_limits<float>::infinity();
        if (fault=="budget") options.max_triangles=1;
        if (fault=="voxel_budget") options.max_voxels=1;
        if (fault=="invalid_budget") options.max_triangles=0;
        if (fault=="empty_surface") for (size_t i=0;i<shape.coords.size();++i) for (int j=3;j<6;++j) shape.values[i*7+j]=0;
        if (fault=="texture_nan") texture.values[0]=std::numeric_limits<float>::infinity();
        pixal::TriangleMesh mesh; pixal::SparseLatent pbr; pixal::MeshDecodeStats stats;
        if (flags.count("--shape")) {
            if (!flags.count("--texture") || !flags.count("--backend")) throw std::invalid_argument("connected decoders require two checkpoints and explicit backend");
            bool gpu=flags.at("--backend")=="vulkan";
            if ((flags.at("--backend")!="cpu" && !gpu) || gpu!=(flags.count("--device")!=0)) throw std::invalid_argument("explicit admitted Vulkan device required");
            pixal::inspect_sparse_decoder_checkpoint(flags.at("--shape")); pixal::inspect_sparse_decoder_checkpoint(flags.at("--texture"));
            std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(gpu?ggml_backend_vk_init(std::stoi(flags.at("--device"))):ggml_backend_cpu_init(),ggml_backend_free);
            if (!backend) throw std::runtime_error("requested mesh decoder backend unavailable");
            if (!gpu) ggml_backend_cpu_set_n_threads(backend.get(),2);
            pixal::SparseDecoderModel sd(flags.at("--shape"),backend.get()),td(flags.at("--texture"),backend.get());
            pixal::SparseDecoderOptions decoder; decoder.f32_arithmetic=true; decoder.chunk_rows=7;
            decoder.progress=[&](int done,int total) { if (done==total) ++decoder_completions; };
            decoder.cancelled=[&]() { return fault=="decoder_cancel" && decoder_completions>0; };
            if (fault=="latent_order") std::swap(texture.coords.front(),texture.coords.back());
            pixal::SurfaceDecodeStats measured;
            auto result=pixal::decode_surface(fault=="model_kind"?td:sd,td,shape,texture,decoder,options,&measured);
            mesh=std::move(result.mesh); pbr=std::move(result.texture); stats=measured.mesh;
            options.progress={}; decoder.progress={};
            auto again=pixal::decode_surface(sd,td,shape,texture,decoder,options);
            if (again.mesh.vertices!=mesh.vertices || again.mesh.faces!=mesh.faces || again.texture.values!=pbr.values || again.texture.coords!=pbr.coords) throw std::runtime_error("connected surface repeat differs");
            std::cout << "backend=" << ggml_backend_name(backend.get()) << " decoder_stages=" << decoder_completions << '\n';
        } else {
            if (flags.count("--backend") || flags.count("--texture") || flags.count("--device")) throw std::invalid_argument("raw mesh geometry does not use a GPU backend");
            mesh=pixal::mesh_from_fields(shape,margin,options,&stats); pbr=pixal::pbr_from_fields(texture,options);
            options.progress={}; auto again=pixal::mesh_from_fields(shape,margin,options);
            if (again.vertices!=mesh.vertices || again.faces!=mesh.faces) throw std::runtime_error("mesh repeat differs");
            if (margin==.5f) {
                trellis::ShapeOut old; old.coords=shape.coords; old.feats7=shape.values; old.res=shape.grid_resolution;
                auto legacy=trellis::dual_grid_to_mesh(old);
                debug["legacy.vertices"]=legacy.verts;
                debug["legacy.faces"]={};
                for (auto v:legacy.faces) debug["legacy.faces"].push_back(float(v));
            }
        }
        for (const auto& v:mesh.vertices) for (float x:v) debug["vertices"].push_back(x);
        debug["faces"]={}; for (const auto& f:mesh.faces) for (int x:f) debug["faces"].push_back(float(x));
        debug["pbr"]=pbr.values; for (const auto& c:pbr.coords) for (int x:c) debug["coords"].push_back(float(x));
        debug["grid"]={float(pbr.grid_resolution)};
        for (const auto& [name,values]:debug) npy::save(directory+"/actual_"+name+".npy",values.data(),{int64_t(values.size())});
        std::cout << "vertices=" << mesh.vertices.size() << " triangles=" << mesh.faces.size() << " intersected=" << stats.intersected_edges
            << " missing_neighbors=" << stats.missing_neighbor_quads << " split02=" << stats.split02 << " split13=" << stats.split13 << " repeat_bitwise=true\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
