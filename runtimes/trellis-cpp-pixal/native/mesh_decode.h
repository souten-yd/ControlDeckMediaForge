#pragma once
#include "sparse_decoder.h"

namespace mediaforge::pixal {
struct TriangleMesh {
    std::vector<std::array<float,3>> vertices;
    std::vector<std::array<int32_t,3>> faces;
};
struct MeshDecodeOptions {
    size_t max_voxels=64*1024*1024, max_triangles=128*1024*1024;
    bool require_faces=true; // false is only useful for raw-field diagnostics
    CancelCheck cancelled;
    Progress progress; // 0..2: vertices, then connectivity
};
struct MeshDecodeStats {
    size_t intersected_edges=0, missing_neighbor_quads=0, split02=0, split13=0;
};
// CPU geometry; preserves voxel order and the upstream quad/triangle winding.
// Does not fill holes, remove unreferenced vertices, simplify or repair topology.
TriangleMesh mesh_from_fields(const SparseLatent& shape,float voxel_margin,
    const MeshDecodeOptions& options={},MeshDecodeStats* stats=nullptr);
// Exact pipeline affine transform (no implicit clamp): base_color RGB,
// metallic, roughness, alpha. Coordinates/grid retain the decoder's ordering.
SparseLatent pbr_from_fields(const SparseLatent& texture,const MeshDecodeOptions& options={});
struct UnrepairedSurface { TriangleMesh mesh; SparseLatent texture; };
struct SurfaceDecodeStats { SparseDecoderStats shape,texture; MeshDecodeStats mesh; };
// Both learned decoders use one caller-owned backend/lease. Shape subdivisions
// are passed directly to texture. MeshWithVoxel.fill_holes is not implemented
// here: this intermediate must be postprocessed before generation is complete.
UnrepairedSurface decode_surface(const SparseDecoderModel& shape_decoder,const SparseDecoderModel& texture_decoder,
    const SparseLatent& shape,const SparseLatent& texture,const SparseDecoderOptions& decoder_options={},
    const MeshDecodeOptions& mesh_options={},SurfaceDecodeStats* stats=nullptr);
}
