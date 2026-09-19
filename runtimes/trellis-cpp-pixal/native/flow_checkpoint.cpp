#include "flow_checkpoint.h"
#include "ggml.h"
#include "gguf.h"
#include <algorithm>
#include <map>
#include <memory>
#include <stdexcept>
#include <vector>

namespace mediaforge::pixal {
FlowCheckpoint inspect_flow_checkpoint(const std::string& path) {
    ggml_context* raw_meta = nullptr;
    gguf_init_params init{true, &raw_meta};
    std::unique_ptr<gguf_context, decltype(&gguf_free)> file(
        gguf_init_from_file(path.c_str(), init), gguf_free);
    std::unique_ptr<ggml_context, decltype(&ggml_free)> meta(raw_meta, ggml_free);
    if (!file || !meta) throw std::invalid_argument("invalid flow GGUF");
    auto key = [&](const std::string& name, gguf_type type) {
        const auto index = gguf_find_key(file.get(), name.c_str());
        if (index < 0 || gguf_get_kv_type(file.get(), index) != type)
            throw std::invalid_argument("flow GGUF missing/invalid key: " + name);
        return index;
    };
    auto string = [&](const std::string& name) -> std::string {
        return gguf_get_val_str(file.get(), key(name, GGUF_TYPE_STRING));
    };
    auto integer = [&](const std::string& name, int minimum, int maximum) {
        const auto value = gguf_get_val_u32(file.get(), key("pixal.flow." + name, GGUF_TYPE_UINT32));
        if (value < (unsigned)minimum || value > (unsigned)maximum)
            throw std::invalid_argument("invalid flow dimension: " + name);
        return (int)value;
    };
    if (string("general.architecture") != "pixal3d-flow" ||
        gguf_get_val_u32(file.get(), key("pixal.schema_version", GGUF_TYPE_UINT32)) != 1 ||
        string("pixal.reference_revision") != "f7cf38429b0bd264f1995f0f8743a88b1c728b94")
        throw std::invalid_argument("unsupported flow GGUF architecture/schema/reference");
    const auto storage = string("pixal.storage");
    if (storage != "f32" && storage != "f16") throw std::invalid_argument("unsupported flow storage");
    for (const auto& name : {"checkpoint_sha256", "config_sha256", "source_revision"}) {
        const auto value = string(std::string("pixal.") + name);
        if (value.size() != (std::string(name) == "source_revision" ? 40 : 64) ||
            value.find_first_not_of("0123456789abcdef") != std::string::npos)
            throw std::invalid_argument("invalid flow source digest/revision");
    }
    const auto source_kind = string("pixal.source_kind");
    if ((source_kind != "synthetic" && source_kind != "checkpoint") || string("pixal.source_repository").empty())
        throw std::invalid_argument("invalid flow provenance");
    FlowCheckpoint result;
    auto& p = result.params;
    p.n_blocks = integer("n_blocks", 1, 64);
    p.n_heads = integer("n_heads", 1, 64);
    p.head_dim = integer("head_dim", 8, 256);
    p.d_model = integer("d_model", 1, 4096);
    p.d_mlp = integer("d_mlp", p.d_model, 16*p.d_model);
    p.d_cond = integer("d_cond", 1, 4096);
    p.proj_in_channels = integer("proj_in_channels", 1, 8192);
    p.in_ch = integer("in_ch", 1, 256);
    p.out_ch = integer("out_ch", 1, 256);
    p.exact_gelu = true;
    result.resolution = integer("resolution", 2, 256);
    result.stage = string("pixal.stage");
    if ((result.stage != "ss" && result.stage != "shape" && result.stage != "texture") ||
        p.d_model != p.n_heads*p.head_dim || p.head_dim % 2 ||
        p.in_ch != p.out_ch*(result.stage == "texture" ? 2 : 1))
        throw std::invalid_argument("invalid flow stage or dimensions");

    std::map<std::string, std::vector<int64_t>> shapes;
    auto linear = [&](const std::string& name, int out, int in) {
        shapes[name + ".weight"] = {in, out};
        shapes[name + ".bias"] = {out};
    };
    linear("input_layer", p.d_model, p.in_ch);
    linear("out_layer", p.out_ch, p.d_model);
    linear("t_embedder.mlp.0", p.d_model, 256);
    linear("t_embedder.mlp.2", p.d_model, p.d_model);
    linear("adaLN_modulation.1", 6*p.d_model, p.d_model);
    for (int i = 0; i < p.n_blocks; ++i) {
        const auto prefix = "blocks." + std::to_string(i) + ".";
        shapes[prefix + "modulation"] = {6*p.d_model};
        shapes[prefix + "norm2.weight"] = {p.d_model};
        shapes[prefix + "norm2.bias"] = {p.d_model};
        linear(prefix + "self_attn.to_qkv", 3*p.d_model, p.d_model);
        linear(prefix + "self_attn.to_out", p.d_model, p.d_model);
        const auto cross = prefix + "cross_attn.cross_attn_block.";
        linear(cross + "to_q", p.d_model, p.d_model);
        linear(cross + "to_kv", 2*p.d_model, p.d_cond);
        linear(cross + "to_out", p.d_model, p.d_model);
        for (const auto& attention : {prefix + "self_attn.", cross})
            for (const auto* norm : {"q_rms_norm.gamma", "k_rms_norm.gamma"})
                shapes[attention + norm] = {p.head_dim, p.n_heads};
        linear(prefix + "cross_attn.proj_linear", p.d_model, p.proj_in_channels);
        linear(prefix + "mlp.mlp.0", p.d_mlp, p.d_model);
        linear(prefix + "mlp.mlp.2", p.d_model, p.d_mlp);
    }
    if (gguf_get_n_tensors(file.get()) != (int64_t)shapes.size())
        throw std::invalid_argument("flow GGUF tensor set mismatch");
    for (const auto& [name, dims] : shapes) {
        auto* tensor = ggml_get_tensor(meta.get(), name.c_str());
        if (!tensor) throw std::invalid_argument("flow GGUF missing tensor: " + name);
        const bool half = storage == "f16" && dims.size() == 2 &&
                          name.size() >= 7 && name.compare(name.size()-7, 7, ".weight") == 0;
        if (tensor->type != (half ? GGML_TYPE_F16 : GGML_TYPE_F32))
            throw std::invalid_argument("flow GGUF tensor type mismatch: " + name);
        for (int i = 0; i < GGML_MAX_DIMS; ++i)
            if (tensor->ne[i] != (i < (int)dims.size() ? dims[i] : 1))
                throw std::invalid_argument("flow GGUF tensor shape mismatch: " + name);
    }
    return result;
}
}
