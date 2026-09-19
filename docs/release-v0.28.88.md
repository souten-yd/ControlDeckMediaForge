# v0.28.88 — Experimental image-to-3D integration

Image-to-3D requests now use MediaForge's existing Scene Jobs, Blender validation,
Asset provenance and Library. The workspace adds capability-driven engine and
resolution selection, CPU preparation progress, cancellation and retry handling.
The additive `media.scene.from_image` tool accepts an image Asset reference.

TRELLIS and Pixal3D adapters require a verified private runtime adoption receipt
and a ControlDeck GPU lease. Neither runtime is adopted on the current installation;
generation remains unavailable. Publishing this release does not establish Vulkan
compatibility, full trained generation, visual quality, rigging or animation.

The source includes the native Pixal port, checkpoint converters and CPU parity
checks. Trained image preparation and bounded trained DINO/flow CPU comparisons
have passed. Full-grid trained generation and Vulkan evaluation remain pending.
Native runtimes, ML environments and model weights are managed separately and are
not included in this lightweight core/UI bundle.

Existing WebP GLB support and registered Library assets are retained. There is no
database migration or Host code change. Before rollback to 0.28.87, allow active
image-to-3D Jobs to finish or cancel them; 0.28.87 does not execute the new operation.
Stored assets and completed Scene revisions remain in the existing managed data.
