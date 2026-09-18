# v0.28.86 — Restore scene create/edit MCP discovery

Expanded scene schemas in 0.28.85 exceeded the Host 64 KiB response bound, so
scene.create/edit disappeared from MCP discovery despite healthy status.
Serve schemas as compact JSON: create/edit are 42,547/42,609 bytes with identical
parsed contracts. Host limits and all schema fields remain unchanged.

All public schema responses are checked against the bound and canonical content.
The previous installed release completed a real OpenCode four-view T-Rex VLM
review and report delivery; this release restores the creation/editing entrypoints.
Visual reviews remain advisory, with no automatic quality approval.
No DB migration, model download, runtime replacement, or Host code change.

Reference-set fields are now explicitly described in the media.generate constraints
schema. Existing required fields and free-form extension support remain unchanged.
This lets local tool decoders express name/views/scale/axes/canonical lineage instead
of reducing a package request to image-oriented asset_brief fields.

Image reviews now receive the actual operation vocabulary plus a null fallback.
Unknown suggestions still remain advisory and fail the existing review gate; no
operation is executed solely because the VLM suggested it.
