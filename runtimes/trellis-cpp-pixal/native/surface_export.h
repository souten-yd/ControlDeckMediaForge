#pragma once
#include "mesh_decode.h"
#include "uv_bake.h"
#include <functional>

namespace mediaforge::pixal {
struct SurfaceExportOptions {
    int texture_size=4096, target_faces=1000000;
    // remesh=false is diagnostic only, not the reference non-remesh pipeline.
    bool remesh=true, webp=true;
    size_t max_glb_bytes=64*1024*1024;
    CancelCheck cancelled;
    std::function<void(const std::string&)> phase;
};
struct SurfaceExportStats {
    size_t original_vertices=0,original_faces=0,remesh_vertices=0,remesh_faces=0;
    size_t simplified_vertices=0,simplified_faces=0,glb_bytes=0;
    int holes_filled=0;
};
struct BakedSurface { trellis::BakedMesh atlas; SurfaceExportStats stats; bool remeshed; };
struct SurfaceProvenance { std::string source_kind,source_sha256,input_sha256; int64_t seed=0; };
// CPU-only postprocessing. Call from a bounded subprocess: charting/remeshing
// can only be interrupted promptly by terminating that caller-owned process.
BakedSurface bake_surface(const UnrepairedSurface& surface,const SurfaceExportOptions& options={});
// Publishes with a same-directory hard link, refusing an existing destination.
// The caller supplies a private allowed output directory, then validates GLB
// independently before creating a Library asset.
SurfaceExportStats export_surface_glb(const BakedSurface& surface,const std::string& path,
    const SurfaceProvenance& provenance,const SurfaceExportOptions& options={});
}
