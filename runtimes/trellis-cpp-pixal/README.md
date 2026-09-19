# Pixal3D native Vulkan port — projection component

This is the first component of the user-requested Pixal3D port onto trellis.cpp.
It is not yet a complete Pixal3D runner and does not enable MediaForge's Pixal3D
capability. The installed trellis.cpp runtime and generated GLBs are unchanged.

The C++ implementation preserves upstream's single-image front-view projection,
Blender coordinate conversion, image pixel-center offset, bilinear border
sampling and sparse coordinate order. Coordinates/indices are planned on the
host; feature gathering and interpolation are a GGML graph using get_rows,
multiply and add. The selected backend must support every graph operation;
the check driver has no scheduler that could silently fall back to CPU.

Fixed external inputs:

- trellis.cpp: `2516c48b677050c570f47eba2e68dc8a5bc918b0`
- its GGML: `737e88f25d4f62254f3b7a726fd9663036cc94da`
- Pixal3D reference: `f7cf38429b0bd264f1995f0f8743a88b1c728b94`

CMake checks source revisions. It links an existing matching trellis.cpp build;
this check is not a claim that an arbitrary build directory has trusted binary
provenance. Evaluation/adoption must also record and verify the library hashes.
No binary, model weight, venv, GPU driver or separate service is shipped here.

```sh
cmake -S runtimes/trellis-cpp-pixal/native -B /tmp/pixal-projection-build \
  -DTRELLIS_SOURCE_DIR="$TRELLIS_SOURCE" -DTRELLIS_BUILD_DIR="$TRELLIS_BUILD"
cmake --build /tmp/pixal-projection-build -j 4
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_projection.py \
  --pixal-source "$PIXAL_SOURCE" \
  --binary /tmp/pixal-projection-build/pixal-projection-check \
  --output-dir "$PIXAL_PROJECTION_REPORT" --backend cpu
```

The checker verifies the pinned, unmodified reference file and executes only
its projection functions/class. It uses synthetic tensors on CPU, without
loading models or importing the full GPU-dependent trainer package. Do not run
it in MediaForge's core environment. The test executable accepts locally
created NPY fixtures only; it is not an untrusted upload endpoint.

After acquiring a genuine Host GPU lease, the same checker can select
`--backend vulkan --device-index N`. The index must be mapped to the actual
broker device. The checker does not acquire, fabricate or verify a Host lease;
its caller owns admission, renewal, termination and release. No Vulkan test
has been executed yet.

Measured CPU results: six cases passed (dense grid, non-power-of-two grid,
one-pixel feature map, border/behind-camera coordinates, reordered/repeated
sparse coordinates, and higher-resolution texture projection). Maximum absolute
error versus upstream torch was `1.621246337890625e-05`; tolerance is
`atol=3e-5, rtol=2e-5`. Invalid scale was rejected. Torch GPU initialized=false.
The upstream computed visibility mask is intentionally not applied, matching
ProjGrid's actual behavior even for behind-camera points.

Evidence: managed data `maintenance/g9-pixal-vulkan-20260919/projection-cpu/`.
Full-model generation, Vulkan numerical parity, performance, memory, visual
quality and Library publication remain NOT TESTED. See
[remaining port work](../../docs/implementation/g9-pixal3d-vulkan-port.md).
