// Private, bounded trained-checkpoint evaluation. No GPU backend initialization.
#include "vision_checkpoint.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "npy.h"
#include <chrono>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <memory>

namespace pixal = mediaforge::pixal;
int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::invalid_argument("usage: pixal-vision-eval-cpu DINO_GGUF RGB_NPY NEW_OUTPUT_DIR");
        const std::filesystem::path output(argv[3]);
        if (std::filesystem::exists(output)) throw std::invalid_argument("output already exists");
        const auto spec = pixal::inspect_vision_checkpoint(argv[1]);
        if (spec.kind != "dino" || spec.source_kind != "checkpoint")
            throw std::invalid_argument("trained DINO checkpoint required");
        if (std::filesystem::file_size(argv[2]) > 16 * 1024 * 1024)
            throw std::invalid_argument("RGB input exceeds bound");
        const auto rgb = npy::load(argv[2]);
        if (rgb.shape.size() != 3 || rgb.shape[0] != 3 || rgb.shape[1] != rgb.shape[2] ||
            (rgb.shape[1] != 256 && rgb.shape[1] != 512 && rgb.shape[1] != 1024))
            throw std::invalid_argument("expected CHW RGB at 256, 512 or 1024 square");
        for (float v : rgb.data) if (!std::isfinite(v) || v < 0 || v > 1)
            throw std::invalid_argument("RGB values must be finite and in [0,1]");
        std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(ggml_backend_cpu_init(), ggml_backend_free);
        if (!backend) throw std::runtime_error("CPU backend unavailable");
        ggml_backend_cpu_set_n_threads(backend.get(), 2);
        const auto start = std::chrono::steady_clock::now();
        pixal::VisionModel dino(argv[1], backend.get());
        const auto features = pixal::encode_vision(dino, nullptr, rgb.data, rgb.shape[1], 0, 0, true);
        for (const auto* values : {&features.dino.global, &features.dino.patches.values})
            for (float v : *values) if (!std::isfinite(v)) throw std::runtime_error("non-finite feature output");
        if (!std::filesystem::create_directory(output)) throw std::runtime_error("output appeared during evaluation");
        try {
            const auto& f = features.dino;
            npy::save((output / "global.npy").string(), f.global.data(), {int64_t(f.global.size() / f.patches.channels), f.patches.channels});
            npy::save((output / "patches.npy").string(), f.patches.values.data(), {f.patches.height, f.patches.width, f.patches.channels});
        } catch (...) { std::filesystem::remove_all(output); throw; }
        const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        std::cout << "backend=cpu arithmetic=f32 image_size=" << rgb.shape[1] << " seconds=" << seconds << '\n';
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
