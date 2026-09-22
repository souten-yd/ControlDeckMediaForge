# Pinned native Vulkan image runtime

Qwen-Image-2.1 uses stable-diffusion.cpp commit
`6dcb5bbd4278aa8f6d851f7515e87555f8e757b7`, including its patched GGML submodule
`4bf5f6000653b7881d00963cd6ddb665ccd62a8d`.
This is a separate build of the existing native runtime, not a new service or
model scheduler. Keep the adopted FLUX/H3 build `97d2990` available.

Build outside the repository and all Python environments, using CMake, Ninja,
a C++ compiler, Vulkan headers/libraries and glslc:

```sh
git clone https://github.com/leejet/stable-diffusion.cpp source
git -C source checkout --detach 6dcb5bbd4278aa8f6d851f7515e87555f8e757b7
git -C source submodule update --init --recursive
cmake -S source -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSD_VULKAN=ON -DSD_HIPBLAS=OFF -DSD_CUDA=OFF \
  -DSD_WEBP=OFF -DSD_WEBM=OFF -DGGML_NATIVE=OFF
cmake --build build --target sd-cli -j 4
build/bin/sd-cli --list-devices
```

The default runtime directory is the Feature data directory's
`runtimes/stable-diffusion-cpp-6dcb5bb-vulkan`. An operator may override it with
`MEDIA_FORGE_NATIVE_VULKAN_RUNTIME_ROOT`. It contains `build/bin/sd-cli` and
`runtime.json`. The latter records the exact source, binary SHA-256 and verified
mapping from Host admission to the Vulkan physical device:

```json
{
  "schema_version": 1,
  "commit": "6dcb5bbd4278aa8f6d851f7515e87555f8e757b7",
  "ggml_commit": "4bf5f6000653b7881d00963cd6ddb665ccd62a8d",
  "backend": "vulkan",
  "binary_sha256": "REPLACE_WITH_SHA256_OF_THIS_BUILD",
  "broker_device_id": "gpu0",
  "vulkan_device_index": 1,
  "device_name": "AMD Radeon AI PRO R9700 (RADV GFX1201)"
}
```

The device index/name above are the measured mapping on the evaluation machine,
not portable defaults. Verify the physical PCI device against Host gpu0 before
writing a profile. The worker exposes just that index to GGML, checks its name
as Vulkan0 and refuses a mismatched lease. Actual inference requires an active
Host lease; device enumeration and compilation do not establish acceptance.
The binary is verified before execution; native children are bound to the
worker lifetime with Linux PDEATHSIG so cancellation cannot leave inference alive.

Model weights remain in the existing model store. Model Management uses its
ordinary license acceptance and atomic, digest-verified installer. Exact component
snapshots already in the shared HF cache may be copied into staging; external
symlink escapes are rejected and cached files still undergo full SHA verification.
Missing runtimes remain unavailable after weights are downloaded.

Qwen is a manual-only research configuration. The existing FLUX default and
ROCm Python dependencies remain unchanged. Only capabilities and dimensions
which pass the [evaluation](../../docs/implementation/qwen-image-21-vulkan-20260922.md)
may be promoted in the catalog.
