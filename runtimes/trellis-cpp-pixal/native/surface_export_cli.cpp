#include "surface_export.h"
#include "tri_bvh.h"
#include "npy.h"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sys/stat.h>

namespace pixal=mediaforge::pixal;
namespace fs=std::filesystem;
int main(int argc,char** argv) {
    fs::path owned;
    try {
        if (argc<7) throw std::invalid_argument("usage: pixal-surface-export input-dir output-dir png|webp synthetic|checkpoint source-sha256 input-sha256 [--diagnostics] [--fault name]");
        fs::path directory=fs::canonical(argv[1]),output=fs::absolute(argv[2]);
        std::string codec=argv[3],fault; bool diagnostics=false;
        for (int i=7;i<argc;++i) {
            std::string flag=argv[i];
            if (flag=="--diagnostics") diagnostics=true;
            else if (flag=="--fault" && i+1<argc) fault=argv[++i];
            else throw std::invalid_argument("invalid surface export argument");
        }
        if (codec!="png" && codec!="webp") throw std::invalid_argument("invalid surface codec");
        if (!fs::create_directory(output)) throw std::invalid_argument("surface output directory exists");
        owned=output; if (chmod(output.c_str(),0700)!=0) throw std::runtime_error("cannot protect surface output directory");
        auto load=[&](const std::string& name) { auto a=npy::load((directory/(name+".npy")).string()); if (a.numel()>16000000) throw std::invalid_argument("surface handoff tensor exceeds bound"); return a; };
        auto v=load("vertices"),f=load("faces"),c=load("coords"),t=load("pbr"),settings=load("settings");
        if (v.data.empty() || f.data.empty() || c.data.empty() || v.shape.size()!=2 || v.shape[1]!=3 || f.shape.size()!=2 || f.shape[1]!=3 || c.shape.size()!=2 || c.shape[1]!=3 || t.shape.size()!=2 || t.shape[1]!=6 || t.shape[0]!=c.shape[0] || settings.data.size()!=5) throw std::invalid_argument("invalid surface handoff dimensions");
        for (float x:settings.data) if (!std::isfinite(x) || x!=std::floor(x) || x<0 || x>1000000) throw std::invalid_argument("invalid surface settings");
        if (settings.data[3]!=0 && settings.data[3]!=1) throw std::invalid_argument("invalid remesh setting");
        pixal::UnrepairedSurface surface;
        for (size_t i=0;i<v.data.size();i+=3) surface.mesh.vertices.push_back({v.data[i],v.data[i+1],v.data[i+2]});
        for (size_t i=0;i<f.data.size();i+=3) {
            std::array<int32_t,3> row;
            for (int j=0;j<3;++j) { float x=f.data[i+j]; if (!std::isfinite(x) || x!=std::floor(x) || x<0 || x>=v.shape[0]) throw std::invalid_argument("invalid surface face index"); row[j]=int32_t(x); }
            surface.mesh.faces.push_back(row);
        }
        for (size_t i=0;i<c.data.size();i+=3) {
            std::array<int,3> row;
            for (int j=0;j<3;++j) { float x=c.data[i+j]; if (!std::isfinite(x) || x!=std::floor(x) || x<0 || x>=settings.data[0]) throw std::invalid_argument("invalid surface voxel coordinate"); row[j]=int(x); }
            surface.texture.coords.push_back(row);
        }
        surface.texture.grid_resolution=int(settings.data[0]); surface.texture.channels=6; surface.texture.values=t.data;
        pixal::SurfaceExportOptions options; options.texture_size=int(settings.data[1]); options.target_faces=int(settings.data[2]); options.remesh=settings.data[3]!=0; options.webp=codec=="webp";
        options.phase=[&](const std::string& phase) { std::cout << "stage=" << phase << std::endl; if (fault=="cancel_"+phase) throw std::runtime_error("surface export cancelled at "+phase); };
        if (fault=="nan_vertex") surface.mesh.vertices[0][0]=std::numeric_limits<float>::quiet_NaN();
        if (fault=="nan_texture") surface.texture.values[0]=std::numeric_limits<float>::infinity();
        if (fault=="duplicate_voxel") surface.texture.coords[0]=surface.texture.coords.back();
        if (fault=="texture_extent") surface.texture.values.pop_back();
        if (fault=="invalid_texture_size") options.texture_size=33;
        if (fault=="byte_budget") options.max_glb_bytes=1024;
        pixal::SurfaceProvenance provenance{argv[4],argv[5],argv[6],int64_t(settings.data[4])};
        if (fault=="invalid_provenance") provenance.input_sha256="invalid";
        auto baked=pixal::bake_surface(surface,options);
        if (fault=="existing_file") { std::ofstream old(output/"asset.glb"); old << "existing"; }
        if (fault=="existing_symlink") fs::create_symlink(directory/"vertices.npy",output/"asset.glb");
        auto stats=pixal::export_surface_glb(baked,(output/"asset.glb").string(),provenance,options);
        if (diagnostics) {
            const auto& b=baked.atlas;
            auto save=[&](const std::string& name,const std::vector<float>& a,int width) { npy::save((output/(name+".npy")).string(),a.data(),{int64_t(a.size()/width),width}); };
            save("vertices",b.verts,3); save("uv",b.uv,2);
            std::vector<float> faces(b.faces.begin(),b.faces.end()),base(b.base.begin(),b.base.end()),mr(b.mr.begin(),b.mr.end());
            save("faces",faces,3);save("base",base,4);save("mr",mr,4);
            if (fs::exists(directory/"queries.npy")) {
                auto q=load("queries");if (q.shape.size()!=2 || q.shape[1]!=3) throw std::invalid_argument("invalid sampler queries");
                for (float x:q.data) if (!std::isfinite(x) || std::abs(x)>16) throw std::invalid_argument("invalid sampler query");
                auto bvh=trellis::TriBvh::build(v.data.data(),int64_t(v.shape[0]),surface.mesh.faces[0].data(),int64_t(surface.mesh.faces.size()));
                trellis::VoxelPbr vox{&surface.texture.coords,&surface.texture.values,surface.texture.grid_resolution,nullptr};
                save("sample_raw",trellis::pixal_sample_pbr(vox,q.data),6);
                vox.snap=&bvh;save("sample_snap",trellis::pixal_sample_pbr(vox,q.data),6);
            }
        }
        std::ofstream report(output/"report.json"); report.exceptions(std::ios::badbit|std::ios::failbit);
        report << "{\"original_vertices\":" << stats.original_vertices << ",\"original_faces\":" << stats.original_faces << ",\"holes_filled\":" << stats.holes_filled
            << ",\"remesh_vertices\":" << stats.remesh_vertices << ",\"remesh_faces\":" << stats.remesh_faces << ",\"simplified_vertices\":" << stats.simplified_vertices
            << ",\"simplified_faces\":" << stats.simplified_faces << ",\"atlas_vertices\":" << baked.atlas.verts.size()/3 << ",\"atlas_faces\":" << baked.atlas.faces.size()/3
            << ",\"texture_size\":" << baked.atlas.T << ",\"glb_bytes\":" << stats.glb_bytes << ",\"codec\":\"" << codec << "\",\"remeshed\":" << (baked.remeshed?"true":"false") << ",\"gpu_execution\":false}\n";
        report.close(); owned.clear(); return 0;
    } catch (const std::exception& e) {
        if (!owned.empty()) { std::error_code error; fs::remove_all(owned,error); }
        std::cerr << e.what() << '\n'; return 1;
    }
}
