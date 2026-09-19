#pragma once
#include "naf.h"
#include <memory>
#include <optional>

namespace mediaforge::pixal {
struct VisionCheckpoint {
    std::string kind, storage, source_kind;
    DinoParams dino;
    NafParams naf;
};
// Validates metadata, complete tensor table and file extents without a backend.
// Local converted artifacts only; not an untrusted Asset upload endpoint.
VisionCheckpoint inspect_vision_checkpoint(const std::string& path);
class VisionModel {
public:
    // Backend is borrowed. No device enumeration/selection or CPU fallback.
    VisionModel(const std::string& path,ggml_backend* backend);
    ~VisionModel();
    VisionModel(const VisionModel&)=delete;
    VisionModel& operator=(const VisionModel&)=delete;
    const trellis::Model& weights() const;
    const VisionCheckpoint& spec() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
struct VisionFeatures { ImageFeatures dino; std::optional<FeatureMap> high; };
// Input is already foreground-framed RGB. Camera estimation is separate.
// Pass naf=nullptr for LR-only SS conditioning; otherwise the caller must pass
// the stage's explicit NAF target size (there is no guessed resolution default).
VisionFeatures encode_vision(const VisionModel& dino,const VisionModel* naf,
                             const std::vector<float>& rgb_chw,int image_size,
                             int high_width=0,int high_height=0,bool f32_arithmetic=false,
                             NafStats* stats=nullptr,
                             std::map<std::string,std::vector<float>>* debug=nullptr,
                             const std::function<bool()>& cancelled={});
}
