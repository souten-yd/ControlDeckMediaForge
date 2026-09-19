// GGUF container loading adapted from trellis.cpp, MIT; see ../NOTICE.
#include "vision_checkpoint.h"
#include "ggml.h"
#include "gguf.h"
#include "ggml-backend.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace mediaforge::pixal {
namespace {
struct CloseFile { void operator()(FILE* file) const { fclose(file); } };
struct Parsed {
    std::unique_ptr<FILE,CloseFile> file;
    trellis::Model model;
    VisionCheckpoint spec;
    ~Parsed() { model.backend=nullptr; model.free(); }
};
std::unique_ptr<Parsed> parse(const std::string& path) {
    auto parsed=std::make_unique<Parsed>(); auto& m=parsed->model; auto& result=parsed->spec;
    parsed->file.reset(fopen(path.c_str(),"rb"));
    if (!parsed->file || fseeko(parsed->file.get(),0,SEEK_END)) throw std::invalid_argument("cannot open vision GGUF");
    const auto length=ftello(parsed->file.get());
    if (length<8 || uint64_t(length)>uint64_t(32)*1024*1024*1024 || fseeko(parsed->file.get(),0,SEEK_SET))
        throw std::invalid_argument("invalid vision GGUF size");
    m.gguf=gguf_init_from_file_ptr(parsed->file.get(),{true,&m.meta});
    if (!m.gguf || !m.meta) throw std::invalid_argument("invalid vision GGUF");
    auto key=[&](const std::string& name,gguf_type type) {
        auto index=gguf_find_key(m.gguf,name.c_str());
        if (index<0 || gguf_get_kv_type(m.gguf,index)!=type) throw std::invalid_argument("vision GGUF missing/invalid key: "+name);
        return index;
    };
    auto string=[&](const std::string& name) -> std::string { return gguf_get_val_str(m.gguf,key(name,GGUF_TYPE_STRING)); };
    auto integer=[&](const std::string& name,int lo,int hi) {
        uint32_t value=gguf_get_val_u32(m.gguf,key("pixal.vision."+name,GGUF_TYPE_UINT32));
        if (value<unsigned(lo) || value>unsigned(hi)) throw std::invalid_argument("invalid vision dimension: "+name);
        return int(value);
    };
    auto real=[&](const std::string& name,float lo,float hi) {
        float value=gguf_get_val_f32(m.gguf,key("pixal.vision."+name,GGUF_TYPE_FLOAT32));
        if (!std::isfinite(value) || value<lo || value>hi) throw std::invalid_argument("invalid vision scalar: "+name);
        return value;
    };
    auto boolean=[&](const std::string& name) { return gguf_get_val_bool(m.gguf,key("pixal.vision."+name,GGUF_TYPE_BOOL)); };
    if (string("general.architecture")!="pixal3d-vision" ||
        gguf_get_val_u32(m.gguf,key("pixal.schema_version",GGUF_TYPE_UINT32))!=1 ||
        string("pixal.reference_revision")!="f7cf38429b0bd264f1995f0f8743a88b1c728b94")
        throw std::invalid_argument("unsupported vision GGUF architecture/schema/reference");
    result.kind=string("pixal.vision.kind"); result.storage=string("pixal.storage"); result.source_kind=string("pixal.source_kind");
    if ((result.kind!="dino" && result.kind!="naf") || (result.storage!="f32" && result.storage!="f16") ||
        (result.source_kind!="synthetic" && result.source_kind!="checkpoint")) throw std::invalid_argument("invalid vision kind/storage/source");
    if (string("pixal.vision.reference_revision")!=(result.kind=="dino" ? "transformers-4.57.3" : "37f2dfc180f2de53d98bd601109c0da0dd6b0f43"))
        throw std::invalid_argument("unsupported vision component reference");
    for (const auto& name:{"checkpoint_sha256","config_sha256","source_revision"}) {
        auto value=string(std::string("pixal.")+name);
        if (value.size()!=(std::string(name)=="source_revision" ? 40 : 64) || value.find_first_not_of("0123456789abcdef")!=std::string::npos)
            throw std::invalid_argument("invalid vision source digest/revision");
    }
    auto format=string("pixal.input_format");
    if (string("pixal.source_repository").empty() || (format!="safetensors" && !(result.kind=="naf" && format=="torch-weights-only")))
        throw std::invalid_argument("invalid vision source provenance");
    std::map<std::string,std::vector<int64_t>> shapes;
    auto linear=[&](const std::string& name,int in,int out,bool bias) {
        shapes[name+".weight"]={in,out}; if (bias) shapes[name+".bias"]={out};
    };
    if (result.kind=="dino") {
        auto& p=result.dino;
        p.channels=integer("channels",8,4096); p.heads=integer("heads",1,128); p.layers=integer("layers",1,48);
        p.patch_size=integer("patch_size",1,32); p.registers=integer("registers",1,16);
        p.mlp_channels=integer("mlp_channels",p.channels,16384);
        p.norm_epsilon=real("norm_epsilon",1e-12f,1.f); p.rope_theta=real("rope_theta",1e-6f,1e6f);
        bool qb=boolean("query_bias"),kb=boolean("key_bias"),vb=boolean("value_bias");
        bool fused=boolean("qkv_bias"),proj=boolean("proj_bias"),mlp=boolean("mlp_bias");
        if (p.channels%p.heads || (p.channels/p.heads)%4 || fused!=(qb||kb||vb)) throw std::invalid_argument("invalid DINO dimensions/bias metadata");
        const int D=p.channels;
        shapes["patch_embed.proj.weight"]={p.patch_size,p.patch_size,3,D}; shapes["patch_embed.proj.bias"]={D};
        shapes["cls_token"]={D,1,1}; shapes["reg_token"]={D,p.registers,1};
        for (int i=0;i<p.layers;++i) {
            auto prefix="blocks."+std::to_string(i);
            for (const auto& norm:{"norm1","norm2"}) for (const auto& part:{"weight","bias"}) shapes[prefix+"."+norm+"."+part]={D};
            linear(prefix+".attn.qkv",D,3*D,fused); linear(prefix+".attn.proj",D,D,proj);
            linear(prefix+".mlp.fc1",D,p.mlp_channels,mlp); linear(prefix+".mlp.fc2",p.mlp_channels,D,mlp);
            shapes[prefix+".gamma_1"]={D}; shapes[prefix+".gamma_2"]={D};
        }
    } else {
        auto& p=result.naf;
        p.channels=integer("channels",16,512); p.heads=integer("heads",1,16); p.rope_heads=integer("rope_heads",1,16);
        p.layers=integer("layers",0,4); p.kernel=integer("kernel",3,15);
        if (p.channels%16 || p.channels%p.heads || p.channels%(4*p.rope_heads) || p.kernel%2==0)
            throw std::invalid_argument("invalid NAF dimensions/kernel metadata");
        const int D=p.channels/2;
        for (const auto& branch:{"encoder","sem_encoder"}) {
            const int kernel=std::string(branch)=="encoder" ? 1 : 3;
            auto prefix=std::string("image_encoder.")+branch;
            shapes[prefix+".0.weight"]={kernel,kernel,3,D}; shapes[prefix+".0.bias"]={D};
            for (int i=1;i<=p.layers;++i) for (int j=1;j<=2;++j) {
                auto name=prefix+"."+std::to_string(i);
                shapes[name+".norm"+std::to_string(j)+".weight"]={D}; shapes[name+".norm"+std::to_string(j)+".bias"]={D};
                shapes[name+".conv"+std::to_string(j)+".weight"]={kernel,kernel,D,D}; shapes[name+".conv"+std::to_string(j)+".bias"]={D};
            }
        }
        shapes["image_encoder.rope.periods"]={p.channels/p.rope_heads/4};
    }
    if (gguf_get_n_tensors(m.gguf)!=int64_t(shapes.size())) throw std::invalid_argument("vision GGUF tensor set mismatch");
    const uint64_t offset=gguf_get_data_offset(m.gguf);
    for (const auto& [name,dims]:shapes) {
        auto* tensor=ggml_get_tensor(m.meta,name.c_str());
        if (!tensor) throw std::invalid_argument("vision GGUF missing tensor: "+name);
        const bool half=result.storage=="f16" && (dims.size()==2 || dims.size()==4) && name.size()>7 && name.compare(name.size()-7,7,".weight")==0;
        if (tensor->type!=(half ? GGML_TYPE_F16 : GGML_TYPE_F32)) throw std::invalid_argument("vision GGUF tensor type mismatch: "+name);
        for (int i=0;i<GGML_MAX_DIMS;++i) if (tensor->ne[i]!=(i<int(dims.size()) ? dims[i] : 1))
            throw std::invalid_argument("vision GGUF tensor shape mismatch: "+name);
        int64_t index=gguf_find_tensor(m.gguf,name.c_str());
        uint64_t relative=gguf_get_tensor_offset(m.gguf,index),bytes=ggml_nbytes(tensor);
        if (offset>uint64_t(length) || relative>uint64_t(length)-offset || bytes>uint64_t(length)-offset-relative)
            throw std::invalid_argument("vision GGUF truncated tensor data: "+name);
        m.tensors[name]=tensor;
    }
    m.arch="pixal3d-vision";
    return parsed;
}
}
VisionCheckpoint inspect_vision_checkpoint(const std::string& path) { return parse(path)->spec; }
struct VisionModel::Impl { std::unique_ptr<Parsed> parsed; };
VisionModel::VisionModel(const std::string& path,ggml_backend* backend) : impl_(std::make_unique<Impl>()) {
    if (!backend) throw std::invalid_argument("explicit vision backend is required");
    impl_->parsed=parse(path); auto& parsed=*impl_->parsed; auto& m=parsed.model;
    m.backend=backend; m.on_gpu=ggml_backend_dev_type(ggml_backend_get_device(backend))!=GGML_BACKEND_DEVICE_TYPE_CPU;
    m.buffer=ggml_backend_alloc_ctx_tensors(m.meta,backend);
    if (!m.buffer) throw std::runtime_error("cannot allocate vision weights on selected backend");
    ggml_backend_buffer_set_usage(m.buffer,GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
    std::vector<uint8_t> staging;
    for (int64_t i=0;i<gguf_get_n_tensors(m.gguf);++i) {
        const auto name=gguf_get_tensor_name(m.gguf,i); auto* tensor=m.get(name);
        uint64_t offset=gguf_get_data_offset(m.gguf)+gguf_get_tensor_offset(m.gguf,i);
        staging.resize(ggml_nbytes(tensor));
        if (fseeko(parsed.file.get(),off_t(offset),SEEK_SET) || fread(staging.data(),1,staging.size(),parsed.file.get())!=staging.size())
            throw std::runtime_error("short read of vision weight");
        const size_t stride=tensor->type==GGML_TYPE_F32 ? 4 : 2;
        const bool periods=std::strcmp(name,"image_encoder.rope.periods")==0;
        for (size_t j=0;j<staging.size();j+=stride) {
            float value;
            if (stride==4) std::memcpy(&value,staging.data()+j,4);
            else { ggml_fp16_t half; std::memcpy(&half,staging.data()+j,2); value=ggml_fp16_to_fp32(half); }
            if (!std::isfinite(value) || (periods && value<=0))
                throw std::invalid_argument("invalid vision weight value: "+std::string(name));
        }
        ggml_backend_tensor_set(tensor,staging.data(),0,staging.size());
    }
    parsed.file.reset();
}
VisionModel::~VisionModel()=default;
const trellis::Model& VisionModel::weights() const { return impl_->parsed->model; }
const VisionCheckpoint& VisionModel::spec() const { return impl_->parsed->spec; }
VisionFeatures encode_vision(const VisionModel& dino,const VisionModel* naf,const std::vector<float>& rgb,int size,
                             int high_width,int high_height,bool f32,NafStats* stats,
                             std::map<std::string,std::vector<float>>* debug,const std::function<bool()>& cancelled) {
    if (dino.spec().kind!="dino" || (naf && (naf->spec().kind!="naf" || naf->weights().backend!=dino.weights().backend)))
        throw std::invalid_argument("vision component kind/backend mismatch");
    if (naf && (high_width<1 || high_height<1 || high_width>1024 || high_height>1024))
        throw std::invalid_argument("explicit supported NAF target size is required");
    auto cancel=[&]() { if (cancelled && cancelled()) throw std::runtime_error("vision encoding cancelled"); };
    cancel(); auto dp=dino.spec().dino; dp.f32_weight_arithmetic=f32;
    std::map<std::string,std::vector<float>> dd,nd;
    VisionFeatures result{encode_dino(dino.weights(),dp,rgb,size,debug ? &dd : nullptr),std::nullopt};
    cancel();
    if (naf) {
        auto np=naf->spec().naf; np.f32_weight_arithmetic=f32;
        result.high=upsample_naf(naf->weights(),np,rgb,size,size,result.dino.patches,high_width,high_height,stats,debug ? &nd : nullptr,cancelled);
    }
    if (debug) {
        for (auto& [name,value]:dd) (*debug)["dino."+name]=std::move(value);
        for (auto& [name,value]:nd) (*debug)["naf."+name]=std::move(value);
    }
    return result;
}
}
