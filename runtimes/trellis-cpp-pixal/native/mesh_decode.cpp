// FlexiDualGrid geometry adapted from pinned trellis.cpp and Pixal/o_voxel.
// See ../NOTICE. All geometry work below runs on the CPU, without GPU kernels.
#include "mesh_decode.h"
#include <cmath>
#include <stdexcept>
#include <unordered_map>

namespace mediaforge::pixal {
namespace {
constexpr int offsets[3][4][3]={
    {{0,0,0},{0,0,1},{0,1,1},{0,1,0}},
    {{0,0,0},{1,0,0},{1,0,1},{0,0,1}},
    {{0,0,0},{0,1,0},{1,1,0},{1,0,0}}
};
void cancel(const MeshDecodeOptions& o) { if (o.cancelled && o.cancelled()) throw std::runtime_error("mesh decoding cancelled"); }
uint64_t key(int x,int y,int z) { return (uint64_t(x)<<42)|(uint64_t(y)<<21)|uint64_t(z); }
using CoordinateMap=std::unordered_map<uint64_t,int32_t>;
CoordinateMap validate(const SparseLatent& input,int channels,const MeshDecodeOptions& o) {
    if (o.max_voxels<1 || o.max_voxels>64*1024*1024 || o.max_triangles<1 || o.max_triangles>256*1024*1024)
        throw std::invalid_argument("invalid mesh decoding budget");
    if (input.grid_resolution<2 || input.grid_resolution>4096 || input.channels!=channels || input.coords.empty() ||
        input.coords.size()>o.max_voxels || input.values.size()!=input.coords.size()*size_t(channels))
        throw std::invalid_argument("invalid mesh field dimensions");
    CoordinateMap lookup; lookup.reserve(input.coords.size());
    for (size_t i=0;i<input.coords.size();++i) {
        if (i%4096==0) cancel(o);
        const auto& c=input.coords[i];
        for (int v:c) if (v<0 || v>=input.grid_resolution) throw std::invalid_argument("mesh coordinate outside grid");
        if (!lookup.emplace(key(c[0],c[1],c[2]),int32_t(i)).second) throw std::invalid_argument("duplicate mesh coordinate");
        for (int j=0;j<channels;++j) if (!std::isfinite(input.values[i*channels+j])) throw std::invalid_argument("non-finite mesh field");
    }
    return lookup;
}
float sigmoid(float x) {
    if (x>=0) return 1.f/(1.f+std::exp(-x));
    float e=std::exp(x); return e/(1.f+e);
}
float softplus(float x) { return x>20.f?x:std::log1p(std::exp(x)); }
}
TriangleMesh mesh_from_fields(const SparseLatent& shape,float margin,const MeshDecodeOptions& o,MeshDecodeStats* stats) {
    if (!std::isfinite(margin) || margin<0 || margin>4) throw std::invalid_argument("invalid voxel margin");
    auto lookup=validate(shape,7,o); cancel(o);
    TriangleMesh result; MeshDecodeStats measured;
    result.vertices.resize(shape.coords.size());
    std::vector<float> splits(shape.coords.size());
    const float voxel_size=1.f/shape.grid_resolution;
    if (o.progress) o.progress(0,2);
    for (size_t i=0;i<shape.coords.size();++i) {
        if (i%4096==0) cancel(o);
        for (int axis=0;axis<3;++axis) {
            float offset=(1.f+2.f*margin)*sigmoid(shape.values[7*i+axis])-margin;
            result.vertices[i][axis]=(float(shape.coords[i][axis])+offset)*voxel_size-.5f;
        }
        splits[i]=softplus(shape.values[7*i+6]);
    }
    if (o.progress) o.progress(1,2);
    cancel(o);
    for (size_t i=0;i<shape.coords.size();++i) {
        if (i%4096==0) cancel(o);
        for (int axis=0;axis<3;++axis) {
            if (!(shape.values[7*i+3+axis]>0)) continue;
            ++measured.intersected_edges;
            std::array<int32_t,4> quad; bool complete=true;
            for (int j=0;j<4;++j) {
                int x=shape.coords[i][0]+offsets[axis][j][0],y=shape.coords[i][1]+offsets[axis][j][1],z=shape.coords[i][2]+offsets[axis][j][2];
                if (x>=shape.grid_resolution || y>=shape.grid_resolution || z>=shape.grid_resolution) { complete=false; break; }
                auto found=lookup.find(key(x,y,z));
                if (found==lookup.end()) { complete=false; break; }
                quad[j]=found->second;
            }
            if (!complete) { ++measured.missing_neighbor_quads; continue; }
            if (result.faces.size()>o.max_triangles || o.max_triangles-result.faces.size()<2)
                throw std::invalid_argument("mesh exceeds explicit triangle budget");
            // Preserve the upstream strict comparison, including equal weights.
            float w02=splits[quad[0]]*splits[quad[2]],w13=splits[quad[1]]*splits[quad[3]];
            if (w02>w13) {
                ++measured.split02;
                result.faces.push_back({quad[0],quad[1],quad[2]}); result.faces.push_back({quad[0],quad[2],quad[3]});
            } else {
                ++measured.split13;
                result.faces.push_back({quad[0],quad[1],quad[3]}); result.faces.push_back({quad[3],quad[1],quad[2]});
            }
        }
    }
    if (o.require_faces && result.faces.empty()) throw std::runtime_error("mesh contains no triangles");
    if (o.progress) o.progress(2,2);
    cancel(o); if (stats) *stats=measured; return result;
}
SparseLatent pbr_from_fields(const SparseLatent& texture,const MeshDecodeOptions& o) {
    validate(texture,6,o); SparseLatent result=texture;
    for (size_t i=0;i<result.values.size();++i) {
        if (i%24576==0) cancel(o);
        result.values[i]=result.values[i]*.5f+.5f;
    }
    cancel(o); return result;
}
UnrepairedSurface decode_surface(const SparseDecoderModel& sd,const SparseDecoderModel& td,const SparseLatent& shape,
    const SparseLatent& texture,const SparseDecoderOptions& decoder_options,const MeshDecodeOptions& mesh_options,SurfaceDecodeStats* stats) {
    if (sd.spec().params.kind!="shape" || td.spec().params.kind!="texture" || sd.weights().backend!=td.weights().backend ||
        sd.spec().params.channels.size()!=td.spec().params.channels.size() || shape.coords!=texture.coords || shape.grid_resolution!=texture.grid_resolution)
        throw std::invalid_argument("surface decoder/model/coordinate/backend mismatch");
    auto cancelled=[&]() { return (decoder_options.cancelled && decoder_options.cancelled()) || (mesh_options.cancelled && mesh_options.cancelled()); };
    SparseDecoderOptions d=decoder_options; d.cancelled=cancelled;
    MeshDecodeOptions m=mesh_options; m.cancelled=cancelled;
    SurfaceDecodeStats measured;
    auto s=decode_sparse(sd,shape,nullptr,d,&measured.shape);
    auto t=decode_sparse(td,texture,&s.subdivisions,d,&measured.texture);
    if (s.fields.coords!=t.fields.coords || s.fields.grid_resolution!=t.fields.grid_resolution) throw std::runtime_error("decoded surface/texture alignment mismatch");
    UnrepairedSurface result;
    result.mesh=mesh_from_fields(s.fields,sd.spec().params.voxel_margin,m,&measured.mesh);
    result.texture=pbr_from_fields(t.fields,m);
    cancel(m); if (stats) *stats=measured; return result;
}
}
