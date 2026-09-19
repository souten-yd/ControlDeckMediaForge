// Strict borrowed-backend GGUF loading, adapted from our vision loader and
// pinned trellis.cpp (MIT; see ../NOTICE).
#include "sparse_decoder.h"
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
    SparseDecoderCheckpoint spec;
    ~Parsed() { model.backend=nullptr; model.free(); }
};
std::unique_ptr<Parsed> parse(const std::string& path) {
    auto result=std::make_unique<Parsed>(); auto& m=result->model; auto& s=result->spec; auto& p=s.params;
    result->file.reset(fopen(path.c_str(),"rb"));
    if (!result->file || fseeko(result->file.get(),0,SEEK_END)) throw std::invalid_argument("cannot open sparse decoder GGUF");
    auto length=ftello(result->file.get());
    if (length<8 || uint64_t(length)>uint64_t(32)*1024*1024*1024 || fseeko(result->file.get(),0,SEEK_SET))
        throw std::invalid_argument("invalid sparse decoder GGUF length");
    m.gguf=gguf_init_from_file_ptr(result->file.get(),{true,&m.meta});
    if (!m.gguf || !m.meta) throw std::invalid_argument("invalid sparse decoder GGUF");
    auto key=[&](const std::string& name,gguf_type type) {
        int64_t i=gguf_find_key(m.gguf,name.c_str());
        if (i<0 || gguf_get_kv_type(m.gguf,i)!=type) throw std::invalid_argument("missing/invalid sparse decoder metadata: "+name);
        return i;
    };
    auto str=[&](const std::string& name)->std::string { return gguf_get_val_str(m.gguf,key(name,GGUF_TYPE_STRING)); };
    auto integer=[&](const std::string& name,int lo,int hi) {
        auto v=gguf_get_val_u32(m.gguf,key("pixal.sparse_decoder."+name,GGUF_TYPE_UINT32));
        if (v<unsigned(lo) || v>unsigned(hi)) throw std::invalid_argument("invalid sparse decoder dimension: "+name);
        return int(v);
    };
    if (str("general.architecture")!="pixal3d-sparse-decoder" || gguf_get_val_u32(m.gguf,key("pixal.schema_version",GGUF_TYPE_UINT32))!=1 ||
        str("pixal.reference_revision")!="f7cf38429b0bd264f1995f0f8743a88b1c728b94") throw std::invalid_argument("unsupported sparse decoder architecture/schema/reference");
    s.storage=str("pixal.storage"); s.source_kind=str("pixal.source_kind");
    if ((s.storage!="f32" && s.storage!="f16") || (s.source_kind!="synthetic" && s.source_kind!="checkpoint") || str("pixal.source_repository").empty())
        throw std::invalid_argument("invalid sparse decoder provenance/storage");
    for (const auto& name:{"checkpoint_sha256","config_sha256","source_revision"}) {
        auto v=str(std::string("pixal.")+name);
        if (v.size()!=(std::string(name)=="source_revision"?40:64) || v.find_first_not_of("0123456789abcdef")!=std::string::npos)
            throw std::invalid_argument("invalid sparse decoder source digest/revision");
    }
    p.kind=str("pixal.sparse_decoder.kind");
    if (p.kind!="shape" && p.kind!="texture") throw std::invalid_argument("invalid sparse decoder kind");
    p.latent_channels=integer("latent_channels",1,64); p.out_channels=integer("out_channels",6,7);
    p.resolution=integer("resolution",p.kind=="shape"?2:0,p.kind=="shape"?4096:0);
    if (p.out_channels!=(p.kind=="shape"?7:6)) throw std::invalid_argument("sparse decoder output/kind mismatch");
    p.voxel_margin=gguf_get_val_f32(m.gguf,key("pixal.sparse_decoder.voxel_margin",GGUF_TYPE_FLOAT32));
    if (!std::isfinite(p.voxel_margin) || p.voxel_margin<0 || p.voxel_margin>4 || (p.kind=="texture" && p.voxel_margin!=0))
        throw std::invalid_argument("invalid sparse decoder voxel margin");
    p.reference_fp16=gguf_get_val_bool(m.gguf,key("pixal.sparse_decoder.reference_fp16",GGUF_TYPE_BOOL));
    int stages=integer("stages",2,5);
    for (int i=0;i<stages;++i) {
        p.channels.push_back(integer("channels."+std::to_string(i),8,2048));
        p.blocks.push_back(integer("blocks."+std::to_string(i),0,32));
        p.mlp_channels.push_back(integer("mlp_channels."+std::to_string(i),p.channels.back()/2,p.channels.back()*16));
        if (i+1<stages && p.mlp_channels.back()!=p.channels.back()*4) throw std::invalid_argument("non-final C2S stage has unsupported MLP ratio");
        if (i && (p.channels[i-1]%8 || p.channels[i]%(p.channels[i-1]/8))) throw std::invalid_argument("invalid C2S skip dimensions");
    }
    std::map<std::string,std::vector<int64_t>> shapes;
    auto linear=[&](const std::string& name,int in,int out) { shapes[name+".weight"]={in,out}; shapes[name+".bias"]={out}; };
    auto conv=[&](const std::string& name,int in,int out) { shapes[name+".weight"]={in,27,out}; shapes[name+".bias"]={out}; };
    auto norm=[&](const std::string& name,int ch) { shapes[name+".weight"]={ch}; shapes[name+".bias"]={ch}; };
    linear("from_latent",p.latent_channels,p.channels[0]); linear("output_layer",p.channels.back(),p.out_channels);
    for (int i=0;i<stages;++i) {
        int ch=p.channels[i];
        for (int j=0;j<p.blocks[i];++j) {
            auto name="blocks."+std::to_string(i)+"."+std::to_string(j);
            conv(name+".conv",ch,ch); norm(name+".norm",ch);
            linear(name+".mlp.0",ch,p.mlp_channels[i]); linear(name+".mlp.2",p.mlp_channels[i],ch);
        }
        if (i+1<stages) {
            auto name="blocks."+std::to_string(i)+"."+std::to_string(p.blocks[i]); int out=p.channels[i+1];
            norm(name+".norm1",ch); conv(name+".conv1",ch,out*8); conv(name+".conv2",out,out);
            if (p.kind=="shape") linear(name+".to_subdiv",ch,8);
        }
    }
    if (gguf_get_n_tensors(m.gguf)!=int64_t(shapes.size())) throw std::invalid_argument("sparse decoder GGUF tensor set mismatch");
    const uint64_t data=gguf_get_data_offset(m.gguf);
    for (const auto& [name,dims]:shapes) {
        auto* t=ggml_get_tensor(m.meta,name.c_str());
        if (!t) throw std::invalid_argument("missing sparse decoder tensor: "+name);
        if (t->type!=(s.storage=="f16" && dims.size()>1 ? GGML_TYPE_F16 : GGML_TYPE_F32)) throw std::invalid_argument("sparse decoder tensor type mismatch: "+name);
        for (int i=0;i<GGML_MAX_DIMS;++i) if (t->ne[i]!=(i<int(dims.size())?dims[i]:1)) throw std::invalid_argument("sparse decoder tensor shape mismatch: "+name);
        auto index=gguf_find_tensor(m.gguf,name.c_str()); uint64_t offset=gguf_get_tensor_offset(m.gguf,index),bytes=ggml_nbytes(t);
        if (data>uint64_t(length) || offset>uint64_t(length)-data || bytes>uint64_t(length)-data-offset)
            throw std::invalid_argument("truncated sparse decoder tensor: "+name);
        m.tensors[name]=t;
    }
    m.arch="pixal3d-sparse-decoder"; return result;
}
}
SparseDecoderCheckpoint inspect_sparse_decoder_checkpoint(const std::string& path) { return parse(path)->spec; }
struct SparseDecoderModel::Impl { std::unique_ptr<Parsed> parsed; };
SparseDecoderModel::SparseDecoderModel(const std::string& path,ggml_backend* backend):impl_(std::make_unique<Impl>()) {
    if (!backend) throw std::invalid_argument("sparse decoder requires explicit borrowed backend");
    impl_->parsed=parse(path); auto& parsed=*impl_->parsed; auto& m=parsed.model;
    m.backend=backend; m.on_gpu=ggml_backend_dev_type(ggml_backend_get_device(backend))!=GGML_BACKEND_DEVICE_TYPE_CPU;
    m.buffer=ggml_backend_alloc_ctx_tensors(m.meta,backend);
    if (!m.buffer) throw std::runtime_error("sparse decoder weight allocation failed");
    ggml_backend_buffer_set_usage(m.buffer,GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
    std::vector<uint8_t> staging;
    for (int64_t i=0;i<gguf_get_n_tensors(m.gguf);++i) {
        auto* t=m.get(gguf_get_tensor_name(m.gguf,i)); staging.resize(ggml_nbytes(t));
        uint64_t offset=gguf_get_data_offset(m.gguf)+gguf_get_tensor_offset(m.gguf,i);
        if (fseeko(parsed.file.get(),off_t(offset),SEEK_SET) || fread(staging.data(),1,staging.size(),parsed.file.get())!=staging.size())
            throw std::runtime_error("short read of sparse decoder weight");
        const size_t stride=t->type==GGML_TYPE_F32?4:2;
        for (size_t j=0;j<staging.size();j+=stride) {
            float v;
            if (stride==4) std::memcpy(&v,staging.data()+j,4);
            else { ggml_fp16_t half; std::memcpy(&half,staging.data()+j,2); v=ggml_fp16_to_fp32(half); }
            if (!std::isfinite(v)) throw std::invalid_argument("non-finite sparse decoder weight");
        }
        ggml_backend_tensor_set(t,staging.data(),0,staging.size());
    }
    parsed.file.reset();
}
SparseDecoderModel::~SparseDecoderModel()=default;
const trellis::Model& SparseDecoderModel::weights() const { return impl_->parsed->model; }
const SparseDecoderCheckpoint& SparseDecoderModel::spec() const { return impl_->parsed->spec; }
}
