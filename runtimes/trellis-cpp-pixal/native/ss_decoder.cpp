// Configurable F32 adaptation of pinned trellis.cpp SS decoder. MIT; ../NOTICE.
#include "ss_decoder.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include <algorithm>
#include <stdexcept>
#include <cmath>

namespace mediaforge::pixal {
namespace {
using T=ggml_tensor;
void finite(const std::vector<float>& values) {
    if (!std::all_of(values.begin(),values.end(),[](float v) { return std::isfinite(v); })) throw std::invalid_argument("non-finite SS decoder activation");
}
void cancel(const SsDecoderOptions& options) {
    if (options.cancelled && options.cancelled()) throw std::runtime_error("SS decoder cancelled");
}
struct Graph {
    ggml_context* ctx=nullptr;
    ggml_gallocr_t allocator=nullptr;
    Graph() {
        ctx=ggml_init({ggml_tensor_overhead()*8192+ggml_graph_overhead_custom(8192,false)+(1<<20),nullptr,true});
        if (!ctx) throw std::runtime_error("SS decoder graph context failed");
    }
    ~Graph() { if (allocator) ggml_gallocr_free(allocator); if (ctx) ggml_free(ctx); }
};
T* weight(ggml_context* c,const trellis::Model& m,const std::string& name) {
    T* t=m.get(name); return t->type==GGML_TYPE_F32?t:ggml_cast(c,t,GGML_TYPE_F32);
}
T* conv(ggml_context* c,const trellis::Model& m,const std::string& name,T* x,int in,int out) {
    T* w=weight(c,m,name+".weight");
    T* y=ggml_conv_3d(c,w,x,in,1,1,1,1,1,1,1,1,1);
    return ggml_add(c,y,ggml_reshape_4d(c,weight(c,m,name+".bias"),1,1,1,out));
}
T* norm(ggml_context* c,const trellis::Model& m,const std::string& name,T* x,bool group=false) {
    if (group) {
        // GGML GroupNorm groups ne2, whereas this volume has channels in ne3.
        T* y=ggml_reshape_4d(c,x,x->ne[0]*x->ne[1],x->ne[2],x->ne[3],1);
        y=ggml_group_norm(c,y,32,1e-5f);
        y=ggml_mul(c,y,ggml_reshape_4d(c,weight(c,m,name+".weight"),1,1,x->ne[3],1));
        y=ggml_add(c,y,ggml_reshape_4d(c,weight(c,m,name+".bias"),1,1,x->ne[3],1));
        return ggml_reshape_4d(c,y,x->ne[0],x->ne[1],x->ne[2],x->ne[3]);
    }
    T* y=ggml_cont(c,ggml_permute(c,x,1,2,3,0));
    y=ggml_norm(c,y,1e-5f); y=ggml_mul(c,y,weight(c,m,name+".weight")); y=ggml_add(c,y,weight(c,m,name+".bias"));
    return ggml_cont(c,ggml_permute(c,y,3,0,1,2));
}
T* block(ggml_context* c,const trellis::Model& m,const std::string& name,T* x,int ch) {
    // Pinned Pixal constructors omit norm_type for all ResBlock3d instances:
    // even a group-normalized decoder uses channel LayerNorm inside its blocks.
    T* y=conv(c,m,name+".conv1",ggml_silu(c,norm(c,m,name+".norm1",x)),ch,ch);
    y=conv(c,m,name+".conv2",ggml_silu(c,norm(c,m,name+".norm2",y)),ch,ch);
    return ggml_add(c,x,y);
}
std::vector<float> shuffle(const std::vector<float>& values,int r,int channels,const SsDecoderOptions& options) {
    int next=r*2; std::vector<float> output(size_t(channels)*next*next*next);
    for (int c=0;c<channels;++c) {
        cancel(options);
        for (int x=0;x<r;++x) for (int y=0;y<r;++y) for (int z=0;z<r;++z) for (int s=0;s<8;++s)
            output[((size_t(c)*next+2*x+(s>>2))*next+2*y+((s>>1)&1))*next+2*z+(s&1)]=values[((size_t(c*8+s)*r+x)*r+y)*r+z];
    }
    return output;
}
}
Occupancy decode_structure(const SsDecoderModel& model,const DenseLatent& latent,const SsDecoderOptions& options,
    SsDecoderStats* stats,std::map<std::string,std::vector<float>>* debug) {
    const auto& p=model.spec().params; const auto& m=model.weights();
    if (p.reference_fp16 && !options.f32_arithmetic) throw std::invalid_argument("FP16 reference decoder requires explicit F32 evaluation; mixed activations are not implemented");
    if (latent.resolution<2 || latent.resolution>32) throw std::invalid_argument("invalid SS decoder latent resolution");
    const int output=latent.resolution*(1<<(p.channels.size()-1));
    if (!m.backend || output>256 || latent.channels!=p.latent_channels ||
        latent.values.size()!=size_t(latent.channels)*latent.resolution*latent.resolution*latent.resolution)
        throw std::invalid_argument("invalid SS decoder latent channels/resolution/extent");
    finite(latent.values); cancel(options);
    SsDecoderStats measured;
    std::map<std::string,std::vector<float>> observed;
    int resolution=latent.resolution,channels=latent.channels,index=0;
    std::vector<float> values=latent.values;
    if (options.progress) options.progress(0,int(p.channels.size()));
    for (size_t stage=0;stage<p.channels.size();++stage) {
        cancel(options); Graph g; auto* c=g.ctx;
        T* input=ggml_new_tensor_4d(c,GGML_TYPE_F32,resolution,resolution,resolution,channels); ggml_set_input(input);
        T* h=input; std::map<std::string,T*> outputs;
        auto keep=[&](const std::string& name,T* t) { if (debug) outputs[name]=t; return t; };
        const int ch=p.channels[stage];
        if (stage==0) {
            h=keep("input_layer",conv(c,m,"input_layer",h,p.latent_channels,ch));
            for (int i=0;i<p.middle_blocks;++i) {
                auto name="middle_block."+std::to_string(i); h=keep(name,block(c,m,name,h,ch));
            }
        }
        for (int i=0;i<p.res_blocks;++i) {
            auto name="blocks."+std::to_string(index++); h=keep(name,block(c,m,name,h,ch));
        }
        if (stage+1<p.channels.size()) {
            auto name="blocks."+std::to_string(index++)+".conv"; h=keep(name,conv(c,m,name,h,ch,p.channels[stage+1]*8));
        } else {
            h=keep("out_layer.0",norm(c,m,"out_layer.0",h,p.norm_type=="group"));
            h=keep("out_layer.1",ggml_silu(c,h)); h=keep("out_layer.2",conv(c,m,"out_layer.2",h,ch,p.out_channels));
        }
        outputs["segment"]=h;
        auto* graph=ggml_new_graph_custom(c,8192,false);
        for (const auto& [name,t]:outputs) {
            (void)name; ggml_set_output(t);
            for (T* owner=t->view_src;owner;owner=owner->view_src) ggml_set_output(owner);
            ggml_build_forward_expand(graph,t);
        }
        for (int i=0;i<ggml_graph_n_nodes(graph);++i) {
            auto* t=ggml_graph_node(graph,i);
            if (!ggml_backend_dev_supports_op(ggml_backend_get_device(m.backend),t))
                throw std::runtime_error(std::string("selected backend cannot execute SS decoder op: ")+ggml_op_name(t->op));
        }
        g.allocator=ggml_gallocr_new(ggml_backend_get_default_buffer_type(m.backend));
        if (!g.allocator || !ggml_gallocr_alloc_graph(g.allocator,graph)) throw std::runtime_error("SS decoder graph allocation failed");
        measured.segment_graph_bytes.push_back(ggml_gallocr_get_buffer_size(g.allocator,0));
        ggml_backend_tensor_set(input,values.data(),0,values.size()*sizeof(float));
        cancel(options);
        if (ggml_backend_graph_compute(m.backend,graph)!=GGML_STATUS_SUCCESS) throw std::runtime_error("SS decoder computation failed");
        cancel(options);
        values=trellis::tensor_to_f32(h); finite(values);
        if (debug) for (const auto& [name,t]:outputs) if (name!="segment") observed[name]=trellis::tensor_to_f32(t);
        if (stage+1<p.channels.size()) {
            channels=p.channels[stage+1]; values=shuffle(values,resolution,channels,options); resolution*=2;
            if (debug) observed["blocks."+std::to_string(index-1)]=values;
        }
        if (options.progress) options.progress(int(stage+1),int(p.channels.size()));
    }
    cancel(options);
    if (stats) *stats=std::move(measured);
    if (debug) *debug=std::move(observed);
    return {output,std::move(values)};
}
Coordinates sample_sparse_structure(const FlowModel& flow,const SsDecoderModel& decoder,const ImageFeatures& image,
    const Camera& camera,const std::vector<float>& noise,int resolution,const StageOptions& flow_options,
    const SsDecoderOptions& decoder_options,SsDecoderStats* stats,std::map<std::string,std::vector<float>>* debug) {
    int decoded=flow.spec().resolution*(1<<(decoder.spec().params.channels.size()-1));
    if (flow.spec().stage!="ss" || flow.spec().resolution>32 || decoded>256 || flow.weights().backend!=decoder.weights().backend ||
        flow.spec().params.out_ch!=decoder.spec().params.latent_channels || resolution<2 || resolution>decoded || decoded%resolution)
        throw std::invalid_argument("SS flow/decoder/grid incompatibility");
    if (decoder.spec().params.reference_fp16 && !decoder_options.f32_arithmetic)
        throw std::invalid_argument("FP16 reference decoder requires explicit F32 evaluation");
    auto combined=decoder_options;
    combined.cancelled=[&]() { return (decoder_options.cancelled && decoder_options.cancelled()) || (flow_options.cancelled && flow_options.cancelled()); };
    cancel(combined);
    auto latent=sample_structure_latent(flow,image,camera,noise,flow_options);
    SsDecoderStats measured;
    std::map<std::string,std::vector<float>> observed;
    auto occupancy=decode_structure(decoder,latent,combined,&measured,debug?&observed:nullptr);
    auto coords=occupancy_coordinates(occupancy.logits,occupancy.resolution,resolution);
    cancel(combined);
    if (stats) *stats=std::move(measured);
    if (debug) { observed["latent"]=std::move(latent.values); observed["logits"]=std::move(occupancy.logits); *debug=std::move(observed); }
    return coords;
}
}
