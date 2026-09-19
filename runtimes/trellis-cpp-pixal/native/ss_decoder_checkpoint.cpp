// Strict borrowed-backend GGUF loading, adapted from our vision loader and
// pinned trellis.cpp (MIT; see ../NOTICE).
#include "ss_decoder.h"
#include "gguf.h"
#include "ggml-backend.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>

namespace mediaforge::pixal {
namespace {
struct CloseFile { void operator()(FILE* file) const { fclose(file); } };
struct Parsed {
    std::unique_ptr<FILE,CloseFile> file;
    trellis::Model model;
    SsDecoderCheckpoint spec;
    ~Parsed() { model.backend=nullptr; model.free(); }
};
std::unique_ptr<Parsed> parse(const std::string& path) {
    auto result=std::make_unique<Parsed>(); auto& m=result->model; auto& s=result->spec; auto& p=s.params;
    result->file.reset(fopen(path.c_str(),"rb"));
    if (!result->file || fseeko(result->file.get(),0,SEEK_END)) throw std::invalid_argument("cannot open SS decoder GGUF");
    auto length=ftello(result->file.get());
    if (length<8 || uint64_t(length)>uint64_t(8)*1024*1024*1024 || fseeko(result->file.get(),0,SEEK_SET))
        throw std::invalid_argument("invalid SS decoder GGUF length");
    m.gguf=gguf_init_from_file_ptr(result->file.get(),{true,&m.meta});
    if (!m.gguf || !m.meta) throw std::invalid_argument("invalid SS decoder GGUF");
    auto key=[&](const std::string& name,gguf_type type) {
        int64_t i=gguf_find_key(m.gguf,name.c_str());
        if (i<0 || gguf_get_kv_type(m.gguf,i)!=type) throw std::invalid_argument("missing/invalid SS decoder metadata: "+name);
        return i;
    };
    auto str=[&](const std::string& name)->std::string { return gguf_get_val_str(m.gguf,key(name,GGUF_TYPE_STRING)); };
    auto integer=[&](const std::string& name,int lo,int hi) {
        auto v=gguf_get_val_u32(m.gguf,key("pixal.ss_decoder."+name,GGUF_TYPE_UINT32));
        if (v<unsigned(lo) || v>unsigned(hi)) throw std::invalid_argument("invalid SS decoder dimension: "+name);
        return int(v);
    };
    if (str("general.architecture")!="pixal3d-ss-decoder" || gguf_get_val_u32(m.gguf,key("pixal.schema_version",GGUF_TYPE_UINT32))!=1 ||
        str("pixal.reference_revision")!="f7cf38429b0bd264f1995f0f8743a88b1c728b94") throw std::invalid_argument("unsupported SS decoder architecture/schema/reference");
    s.storage=str("pixal.storage"); s.source_kind=str("pixal.source_kind");
    if ((s.storage!="f32" && s.storage!="f16") || (s.source_kind!="synthetic" && s.source_kind!="checkpoint") || str("pixal.source_repository").empty())
        throw std::invalid_argument("invalid SS decoder provenance/storage");
    for (const auto& name:{"checkpoint_sha256","config_sha256","source_revision"}) {
        auto v=str(std::string("pixal.")+name);
        if (v.size()!=(std::string(name)=="source_revision"?40:64) || v.find_first_not_of("0123456789abcdef")!=std::string::npos)
            throw std::invalid_argument("invalid SS decoder source digest/revision");
    }
    p.latent_channels=integer("latent_channels",1,64); p.out_channels=integer("out_channels",1,1);
    p.res_blocks=integer("num_res_blocks",0,8); p.middle_blocks=integer("num_res_blocks_middle",0,8);
    int stages=integer("stages",1,5); p.channels.clear();
    for (int i=0;i<stages;++i) p.channels.push_back(integer("channels."+std::to_string(i),2,1024));
    p.norm_type=str("pixal.ss_decoder.norm_type");
    p.reference_fp16=gguf_get_val_bool(m.gguf,key("pixal.ss_decoder.reference_fp16",GGUF_TYPE_BOOL));
    if ((p.norm_type!="layer" && p.norm_type!="group") || (p.norm_type=="group" && p.channels.back()%32))
        throw std::invalid_argument("invalid SS decoder normalization");
    std::map<std::string,std::vector<int64_t>> shapes;
    auto conv=[&](const std::string& name,int in,int out) { shapes[name+".weight"]={3,3,3,int64_t(in)*out}; shapes[name+".bias"]={out}; };
    auto norm=[&](const std::string& name,int ch) { shapes[name+".weight"]={ch}; shapes[name+".bias"]={ch}; };
    auto block=[&](const std::string& name,int ch) {
        for (int j=1;j<=2;++j) { norm(name+".norm"+std::to_string(j),ch); conv(name+".conv"+std::to_string(j),ch,ch); }
    };
    conv("input_layer",p.latent_channels,p.channels[0]);
    for (int i=0;i<p.middle_blocks;++i) block("middle_block."+std::to_string(i),p.channels[0]);
    int index=0;
    for (int i=0;i<stages;++i) {
        for (int j=0;j<p.res_blocks;++j) block("blocks."+std::to_string(index++),p.channels[i]);
        if (i+1<stages) conv("blocks."+std::to_string(index++)+".conv",p.channels[i],p.channels[i+1]*8);
    }
    norm("out_layer.0",p.channels.back()); conv("out_layer.2",p.channels.back(),p.out_channels);
    if (gguf_get_n_tensors(m.gguf)!=int64_t(shapes.size())) throw std::invalid_argument("SS decoder GGUF tensor set mismatch");
    const uint64_t data=gguf_get_data_offset(m.gguf);
    for (const auto& [name,dims]:shapes) {
        auto* t=ggml_get_tensor(m.meta,name.c_str());
        if (!t) throw std::invalid_argument("missing SS decoder tensor: "+name);
        if (t->type!=(s.storage=="f16" && dims.size()==4 ? GGML_TYPE_F16 : GGML_TYPE_F32)) throw std::invalid_argument("SS decoder tensor type mismatch: "+name);
        for (int i=0;i<GGML_MAX_DIMS;++i) if (t->ne[i]!=(i<int(dims.size())?dims[i]:1)) throw std::invalid_argument("SS decoder tensor shape mismatch: "+name);
        auto index=gguf_find_tensor(m.gguf,name.c_str()); uint64_t offset=gguf_get_tensor_offset(m.gguf,index),bytes=ggml_nbytes(t);
        if (data>uint64_t(length) || offset>uint64_t(length)-data || bytes>uint64_t(length)-data-offset)
            throw std::invalid_argument("truncated SS decoder tensor: "+name);
        m.tensors[name]=t;
    }
    m.arch="pixal3d-ss-decoder"; return result;
}
}
SsDecoderCheckpoint inspect_ss_decoder_checkpoint(const std::string& path) { return parse(path)->spec; }
struct SsDecoderModel::Impl { std::unique_ptr<Parsed> parsed; };
SsDecoderModel::SsDecoderModel(const std::string& path,ggml_backend* backend):impl_(std::make_unique<Impl>()) {
    if (!backend) throw std::invalid_argument("SS decoder requires explicit borrowed backend");
    impl_->parsed=parse(path); auto& parsed=*impl_->parsed; auto& m=parsed.model;
    m.backend=backend; m.on_gpu=ggml_backend_dev_type(ggml_backend_get_device(backend))!=GGML_BACKEND_DEVICE_TYPE_CPU;
    m.buffer=ggml_backend_alloc_ctx_tensors(m.meta,backend);
    if (!m.buffer) throw std::runtime_error("SS decoder weight allocation failed");
    ggml_backend_buffer_set_usage(m.buffer,GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
    std::vector<uint8_t> staging;
    for (int64_t i=0;i<gguf_get_n_tensors(m.gguf);++i) {
        auto* t=m.get(gguf_get_tensor_name(m.gguf,i)); staging.resize(ggml_nbytes(t));
        uint64_t offset=gguf_get_data_offset(m.gguf)+gguf_get_tensor_offset(m.gguf,i);
        if (fseeko(parsed.file.get(),off_t(offset),SEEK_SET) || fread(staging.data(),1,staging.size(),parsed.file.get())!=staging.size())
            throw std::runtime_error("short read of SS decoder weight");
        const size_t stride=t->type==GGML_TYPE_F32?4:2;
        for (size_t j=0;j<staging.size();j+=stride) {
            float v;
            if (stride==4) std::memcpy(&v,staging.data()+j,4);
            else { ggml_fp16_t half; std::memcpy(&half,staging.data()+j,2); v=ggml_fp16_to_fp32(half); }
            if (!std::isfinite(v)) throw std::invalid_argument("non-finite SS decoder weight");
        }
        ggml_backend_tensor_set(t,staging.data(),0,staging.size());
    }
    parsed.file.reset();
}
SsDecoderModel::~SsDecoderModel()=default;
const trellis::Model& SsDecoderModel::weights() const { return impl_->parsed->model; }
const SsDecoderCheckpoint& SsDecoderModel::spec() const { return impl_->parsed->spec; }
}
