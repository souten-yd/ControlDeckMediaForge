# v0.28.87 — Import GLB assets with WebP textures

GLB files exported by trellis.cpp can now be imported into the existing Library
without converting embedded WebP textures to PNG. `EXT_texture_webp` is accepted
as a required extension, with bounded image references, WebP MIME validation,
and required/used declaration checks. Original GLB bytes and generator metadata
are preserved, and import provenance records validator version 1.1.0.

Unknown required extensions and external image/buffer URIs remain rejected.
No DB migration, model download, runtime replacement, or Host code change.

Rolling back to 0.28.86 retains stored assets, but its validator rejects required
WebP extensions; use PNG copies or upgrade again when reading these GLBs.
