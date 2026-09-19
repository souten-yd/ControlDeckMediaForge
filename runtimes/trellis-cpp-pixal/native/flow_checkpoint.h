#pragma once
#include "dit.h"
#include <string>

namespace mediaforge::pixal {
struct FlowCheckpoint {
    trellis::DiTParams params;
    int resolution;
    std::string stage;
};
// Inspect metadata and every weight name/type/shape BEFORE allocating a backend.
// Input is a trusted local converted checkpoint, never a public asset upload.
FlowCheckpoint inspect_flow_checkpoint(const std::string& path);
}
