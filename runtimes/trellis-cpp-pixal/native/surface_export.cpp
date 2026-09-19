#include "surface_export.h"
#include "tri_bvh.h"
#include "remesh_dc.h"
#include "mesh_glb.h"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <stdexcept>
#include <unordered_set>
#include <unistd.h>

namespace mediaforge::pixal {
namespace {
void cancel(const SurfaceExportOptions& o) { if (o.cancelled && o.cancelled()) throw std::runtime_error("surface export cancelled"); }
void phase(const SurfaceExportOptions& o,const std::string& name) { cancel(o); if (o.phase) o.phase(name); cancel(o); }
void validate_options(const SurfaceExportOptions& o) {
    if (o.texture_size<32 || o.texture_size>4096 || (o.texture_size&(o.texture_size-1)) || o.target_faces<4 || o.target_faces>5000000 ||
        o.max_glb_bytes<1024 || o.max_glb_bytes>64*1024*1024) throw std::invalid_argument("invalid surface export options");
}
void validate_mesh(const std::vector<float>& v,const std::vector<int32_t>& f) {
    if (v.empty() || f.empty() || v.size()%3 || f.size()%3 || v.size()/3>16000000 || f.size()/3>16000000)
        throw std::invalid_argument("invalid surface mesh dimensions");
    for (float x:v) if (!std::isfinite(x) || std::abs(x)>16) throw std::invalid_argument("invalid surface vertex");
    for (auto i:f) if (i<0 || size_t(i)>=v.size()/3) throw std::invalid_argument("surface face index outside vertex buffer");
}
void validate_texture(const SparseLatent& t) {
    if (t.channels!=6 || t.grid_resolution<2 || t.grid_resolution>1536 || t.coords.empty() || t.coords.size()>16000000 || t.values.size()!=6*t.coords.size())
        throw std::invalid_argument("invalid surface texture dimensions");
    std::unordered_set<uint64_t> seen;
    for (const auto& c:t.coords) {
        for (int x:c) if (x<0 || x>=t.grid_resolution) throw std::invalid_argument("surface texture coordinate outside grid");
        uint64_t key=(uint64_t(c[0])<<42)|(uint64_t(c[1])<<21)|uint64_t(c[2]);
        if (!seen.insert(key).second) throw std::invalid_argument("duplicate surface texture coordinate");
    }
    for (float x:t.values) if (!std::isfinite(x)) throw std::invalid_argument("non-finite surface texture");
}
void validate_baked(const trellis::BakedMesh& b) {
    validate_mesh(b.verts,b.faces);
    if (b.T<32 || b.T>4096 || b.uv.size()!=b.verts.size()/3*2 || b.base.size()!=size_t(b.T)*b.T*4 || b.mr.size()!=b.base.size())
        throw std::runtime_error("invalid baked surface dimensions");
    for (float x:b.uv) if (!std::isfinite(x) || x<0 || x>1.00001f) throw std::runtime_error("invalid baked surface UV");
    for (size_t i=0;i<b.mr.size();i+=4) if (b.mr[i]!=0 || b.mr[i+3]!=255) throw std::runtime_error("invalid baked metallic-roughness layout");
}
struct TemporaryFile {
    std::string path;
    explicit TemporaryFile(const std::filesystem::path& parent) {
        path=(parent/".pixal-glb-XXXXXX").string();
        int fd=mkstemp(path.data()); if (fd<0) throw std::runtime_error("cannot create private GLB staging file"); close(fd);
    }
    ~TemporaryFile() { if (!path.empty()) unlink(path.c_str()); }
};
}
BakedSurface bake_surface(const UnrepairedSurface& input,const SurfaceExportOptions& o) {
    validate_options(o); cancel(o); validate_texture(input.texture);
    std::vector<float> vertices; std::vector<int32_t> faces;
    for (const auto& v:input.mesh.vertices) vertices.insert(vertices.end(),v.begin(),v.end());
    for (const auto& f:input.mesh.faces) faces.insert(faces.end(),f.begin(),f.end());
    validate_mesh(vertices,faces); BakedSurface result; result.remeshed=o.remesh;
    auto& s=result.stats; s.original_vertices=vertices.size()/3; s.original_faces=faces.size()/3;
    phase(o,"holes");
    // decode_latent and to_glb each run this step in the reference pipeline.
    s.holes_filled=trellis::fill_holes(vertices,faces,.03f);
    s.holes_filled+=trellis::fill_holes(vertices,faces,.03f);
    validate_mesh(vertices,faces); phase(o,"bvh");
    auto bvh=trellis::TriBvh::build(vertices.data(),int64_t(vertices.size()/3),faces.data(),int64_t(faces.size()/3));
    if (bvh.empty()) throw std::runtime_error("surface BVH is empty");
    std::vector<float> prepared_vertices; std::vector<int32_t> prepared_faces;
    if (o.remesh) {
        phase(o,"remesh");
        auto mesh=trellis::remesh_narrow_band_dc(vertices.data(),int64_t(vertices.size()/3),faces.data(),int64_t(faces.size()/3),bvh,input.texture.grid_resolution,1,0.f);
        if (mesh.faces.empty()) throw std::runtime_error("surface remesh produced no faces");
        prepared_vertices=std::move(mesh.verts); prepared_faces=std::move(mesh.faces);
    } else { prepared_vertices=vertices; prepared_faces=faces; }
    validate_mesh(prepared_vertices,prepared_faces); s.remesh_vertices=prepared_vertices.size()/3; s.remesh_faces=prepared_faces.size()/3;
    phase(o,"simplify"); std::vector<float> simplified; std::vector<int32_t> simplified_faces;
    trellis::decimate_qem(prepared_vertices,int(prepared_vertices.size()/3),prepared_faces,int(prepared_faces.size()/3),o.target_faces,simplified,simplified_faces);
    validate_mesh(simplified,simplified_faces); s.simplified_vertices=simplified.size()/3; s.simplified_faces=simplified_faces.size()/3;
    phase(o,"uv"); trellis::VoxelPbr volume{&input.texture.coords,&input.texture.values,input.texture.grid_resolution,&bvh};
    result.atlas=trellis::uv_bake(simplified,int(simplified.size()/3),simplified_faces,int(simplified_faces.size()/3),{},o.texture_size,&volume);
    if (!result.atlas.ok()) throw std::runtime_error("surface UV/bake failed; no fallback atlas");
    validate_baked(result.atlas); phase(o,"baked"); return result;
}
SurfaceExportStats export_surface_glb(const BakedSurface& surface,const std::string& path,const SurfaceProvenance& p,const SurfaceExportOptions& o) {
    validate_options(o); validate_baked(surface.atlas); cancel(o);
    if ((p.source_kind!="synthetic" && p.source_kind!="checkpoint") || p.seed<0) throw std::invalid_argument("invalid surface provenance");
    for (const auto& hash:{p.source_sha256,p.input_sha256}) if (hash.size()!=64 || hash.find_first_not_of("0123456789abcdef")!=std::string::npos) throw std::invalid_argument("invalid surface provenance hash");
    auto destination=std::filesystem::path(path);
    if (destination.filename().empty() || destination.filename()=="." || destination.filename()=="..") throw std::invalid_argument("invalid GLB destination");
    auto parent=std::filesystem::canonical(destination.parent_path()); destination=parent/destination.filename();
    if (std::filesystem::symlink_status(destination).type()!=std::filesystem::file_type::not_found) throw std::invalid_argument("GLB destination exists; refusing overwrite");
    TemporaryFile staging(parent); const auto& b=surface.atlas;
    std::string provenance="{\"source_kind\":\""+p.source_kind+"\",\"source_sha256\":\""+p.source_sha256+"\",\"input_sha256\":\""+p.input_sha256+"\",\"reference_revision\":\"f7cf38429b0bd264f1995f0f8743a88b1c728b94\",\"experimental\":true}";
    phase(o,"encode");
    if (!trellis::write_glb_textured(staging.path.c_str(),b.verts.data(),int64_t(b.verts.size()/3),b.uv.data(),b.faces.data(),int64_t(b.faces.size()/3),b.base.data(),b.mr.data(),b.T,!surface.remeshed,p.seed,nullptr,o.webp,provenance.c_str())) throw std::runtime_error("surface GLB encoder failed");
    auto size=std::filesystem::file_size(staging.path);
    if (size<20 || size>o.max_glb_bytes) throw std::runtime_error("surface GLB exceeds explicit byte budget");
    phase(o,"publish");
    if (link(staging.path.c_str(),destination.c_str())!=0) throw std::runtime_error("cannot publish GLB without overwrite");
    auto stats=surface.stats; stats.glb_bytes=size; return stats;
}
}
