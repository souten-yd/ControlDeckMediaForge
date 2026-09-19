// DINO GGML graph adapted from pinned trellis.cpp src/dinov3.cpp (MIT).
// Feature selection/projection follows pinned Pixal3D. See ../NOTICE.
#include "image_features.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-alloc.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mediaforge::pixal {
namespace {
using T = ggml_tensor;
struct Graph {
    ggml_context* ctx = ggml_init({ggml_tensor_overhead()*16384 + ggml_graph_overhead_custom(16384,false)+(1<<20),nullptr,true});
    ggml_gallocr_t alloc = nullptr;
    ggml_cgraph* graph = nullptr;
    Graph() { if (!ctx) throw std::runtime_error("cannot allocate image graph metadata"); }
    ~Graph() { if (alloc) ggml_gallocr_free(alloc); ggml_free(ctx); }
    void allocate(ggml_backend* backend, const std::vector<T*>& outputs) {
        if (!backend) throw std::invalid_argument("explicit image backend is required");
        graph=ggml_new_graph_custom(ctx,16384,false);
        for (auto* t: outputs) { ggml_set_output(t); ggml_build_forward_expand(graph,t); }
        for (int i=0;i<ggml_graph_n_nodes(graph);++i)
            if (!ggml_backend_dev_supports_op(ggml_backend_get_device(backend),ggml_graph_node(graph,i)))
                throw std::runtime_error("selected backend cannot execute image graph operation");
        alloc=ggml_gallocr_new(ggml_backend_get_default_buffer_type(backend));
        if (!alloc || !ggml_gallocr_alloc_graph(alloc,graph)) throw std::runtime_error("image graph allocation failed");
    }
    void compute(ggml_backend* backend) {
        if (ggml_backend_graph_compute(backend,graph)!=GGML_STATUS_SUCCESS) throw std::runtime_error("image graph compute failed");
    }
};
void finite(const std::vector<float>& values) {
    for (float v:values) if (!std::isfinite(v)) throw std::invalid_argument("non-finite image feature/input");
}
void upload(T* tensor,const std::vector<float>& values) { ggml_backend_tensor_set(tensor,values.data(),0,values.size()*sizeof(float)); }
T* weight(const trellis::Model& m,const std::string& name,std::initializer_list<int64_t> dims) {
    auto* tensor=m.get(name);
    if (tensor->type!=GGML_TYPE_F32 && tensor->type!=GGML_TYPE_F16) throw std::invalid_argument("unsupported DINO weight type: "+name);
    int axis=0;
    for (auto size:dims) if (tensor->ne[axis++]!=size) throw std::invalid_argument("DINO weight shape mismatch: "+name);
    for (;axis<GGML_MAX_DIMS;++axis) if (tensor->ne[axis]!=1) throw std::invalid_argument("DINO weight rank mismatch: "+name);
    return tensor;
}
void validate_map(const FeatureMap& map) {
    if (map.channels<1 || map.channels>4096 || map.width<1 || map.height<1 ||
        map.width>2048 || map.height>2048 || map.values.size()!=size_t(map.channels)*map.width*map.height)
        throw std::invalid_argument("invalid feature map dimensions");
    finite(map.values);
}
}
ImageFeatures encode_dino(const trellis::Model& m,const DinoParams& p,const std::vector<float>& rgb,int S,
                          std::map<std::string,std::vector<float>>* debug) {
    if (p.channels<8 || p.channels>4096 || p.heads<1 || p.channels%p.heads ||
        (p.channels/p.heads)%4 || p.layers<1 || p.layers>48 || p.patch_size<1 || p.patch_size>32 ||
        p.registers<1 || p.registers>16 || p.mlp_channels<p.channels || p.mlp_channels>16384 ||
        !std::isfinite(p.norm_epsilon) || p.norm_epsilon<=0 || !std::isfinite(p.rope_theta) || p.rope_theta<=0 ||
        S<p.patch_size || S>1024 || S%p.patch_size || rgb.size()!=size_t(3)*S*S)
        throw std::invalid_argument("invalid DINO configuration/image shape");
    finite(rgb);
    for (float v:rgb) if (v<0 || v>1) throw std::invalid_argument("DINO RGB must be in [0,1]");
    const int D=p.channels,H=p.heads,HD=D/H,grid=S/p.patch_size,NP=grid*grid,prefix=1+p.registers,N=NP+prefix;
    if (N>16389) throw std::invalid_argument("DINO token budget exceeded");
    Graph g; auto* c=g.ctx;
    std::map<std::string,T*> tensors;
    auto keep=[&](const std::string& name,T* t) { if (debug) tensors[name]=t; return t; };
    auto w=[&](const std::string& name,std::initializer_list<int64_t> dims) {
        auto* t=weight(m,name,dims);
        return p.f32_weight_arithmetic && t->type!=GGML_TYPE_F32 ? ggml_cast(c,t,GGML_TYPE_F32) : t;
    };
    auto linear=[&](const std::string& name,T* x,int out) {
        T* y=ggml_mul_mat(c,w(name+".weight",{x->ne[0],out}),x);
        if (m.has(name+".bias")) y=ggml_add(c,y,w(name+".bias",{out}));
        return y;
    };
    auto norm=[&](T* x,const std::string& name) {
        T* y=ggml_norm(c,x,p.norm_epsilon);
        return ggml_add(c,ggml_mul(c,y,w(name+".weight",{D})),w(name+".bias",{D}));
    };
    T* image=ggml_new_tensor_4d(c,GGML_TYPE_F32,S,S,3,1); ggml_set_input(image);
    T* cosine=ggml_new_tensor_3d(c,GGML_TYPE_F32,HD,1,N); ggml_set_input(cosine);
    T* sine=ggml_new_tensor_3d(c,GGML_TYPE_F32,HD,1,N); ggml_set_input(sine);
    auto rotate=[&](T* x) {
        auto* a=ggml_cont(c,ggml_view_3d(c,x,HD/2,H,N,x->nb[1],x->nb[2],0));
        auto* b=ggml_cont(c,ggml_view_3d(c,x,HD/2,H,N,x->nb[1],x->nb[2],(HD/2)*x->nb[0]));
        auto* swapped=ggml_concat(c,ggml_scale(c,b,-1.f),a,0);
        return ggml_add(c,ggml_mul(c,x,cosine),ggml_mul(c,swapped,sine));
    };
    T* patches=ggml_conv_2d(c,w("patch_embed.proj.weight",{p.patch_size,p.patch_size,3,D}),image,p.patch_size,p.patch_size,0,0,1,1);
    patches=ggml_reshape_2d(c,ggml_cont(c,ggml_permute(c,patches,1,2,0,3)),D,NP);
    patches=ggml_add(c,patches,w("patch_embed.proj.bias",{D}));
    T* cls=ggml_cast(c,ggml_reshape_2d(c,w("cls_token",{D,1,1}),D,1),GGML_TYPE_F32);
    T* reg=ggml_cast(c,ggml_reshape_2d(c,w("reg_token",{D,p.registers,1}),D,p.registers),GGML_TYPE_F32);
    T* x=keep("embedding",ggml_concat(c,ggml_concat(c,cls,reg,1),patches,1));
    for (int i=0;i<p.layers;++i) {
        const auto b="blocks."+std::to_string(i);
        T* y=norm(x,b+".norm1");
        T* qkv=ggml_reshape_4d(c,linear(b+".attn.qkv",y,3*D),HD,H,3,N);
        auto select=[&](int index) { return ggml_reshape_3d(c,ggml_cont(c,ggml_view_4d(c,qkv,HD,H,1,N,qkv->nb[1],qkv->nb[2],qkv->nb[3],index*qkv->nb[2])),HD,H,N); };
        T* q=rotate(select(0)),*k=rotate(select(1)),*v=select(2);
        q=ggml_cont(c,ggml_permute(c,q,0,2,1,3)); k=ggml_cont(c,ggml_permute(c,k,0,2,1,3));
        T* attention=ggml_soft_max_ext(c,ggml_mul_mat(c,k,q),nullptr,1.f/std::sqrt(float(HD)),0.f);
        v=ggml_cont(c,ggml_permute(c,v,1,2,0,3));
        y=ggml_reshape_2d(c,ggml_cont(c,ggml_permute(c,ggml_mul_mat(c,v,attention),0,2,1,3)),D,N);
        y=keep(b+".attention",linear(b+".attn.proj",y,D));
        x=ggml_add(c,x,ggml_mul(c,y,w(b+".gamma_1",{D})));
        y=norm(x,b+".norm2");
        y=ggml_gelu_erf(c,linear(b+".mlp.fc1",y,p.mlp_channels));
        y=keep(b+".mlp",linear(b+".mlp.fc2",y,D));
        x=keep(b+".output",ggml_add(c,x,ggml_mul(c,y,w(b+".gamma_2",{D}))));
    }
    // Pixal bypasses HF model.norm affine parameters and applies F.layer_norm.
    x=keep("tokens",ggml_norm(c,x,1e-5f));
    std::vector<T*> outputs{x};
    for (const auto& item:tensors) outputs.push_back(item.second);
    g.allocate(m.backend,outputs);
    std::vector<float> normalized(rgb),rcos(size_t(N)*HD,1.f),rsin(size_t(N)*HD,0.f);
    const float means[]={.485f,.456f,.406f},stds[]={.229f,.224f,.225f};
    for (int ch=0;ch<3;++ch) for (int i=0;i<S*S;++i) normalized[ch*S*S+i]=(rgb[ch*S*S+i]-means[ch])/stds[ch];
    for (int token=0;token<NP;++token) for (int d=0;d<HD;++d) {
        const int position=d%(HD/2),axis=position/(HD/4),frequency=position%(HD/4);
        const float coord=((axis==0 ? token/grid : token%grid)+.5f)/grid*2.f-1.f;
        const float angle=6.283185307179586f*coord/std::pow(p.rope_theta,float(frequency)/(HD/4));
        rcos[size_t(token+prefix)*HD+d]=std::cos(angle); rsin[size_t(token+prefix)*HD+d]=std::sin(angle);
    }
    upload(image,normalized); upload(cosine,rcos); upload(sine,rsin); g.compute(m.backend);
    auto values=trellis::tensor_to_f32(x); finite(values);
    if (debug) { for (const auto& [name,t]:tensors) (*debug)[name]=trellis::tensor_to_f32(t); (*debug)["normalized"]=normalized; }
    const auto split=values.begin()+size_t(prefix)*D;
    return {{values.begin(),split},{D,grid,grid,{split,values.end()}}};
}

ConditionPair image_conditions(ggml_backend* backend,const ImageFeatures& features,
                               const std::vector<std::array<int,3>>& coords,int grid_resolution,
                               const Camera& camera,const FeatureMap* high) {
    validate_map(features.patches); finite(features.global);
    if (features.global.empty() || features.global.size()%features.patches.channels ||
        features.global.size()/features.patches.channels>17) throw std::invalid_argument("invalid DINO global tokens");
    if (high) { validate_map(*high); if (high->channels!=features.patches.channels) throw std::invalid_argument("NAF feature channel mismatch"); }
    Graph g;
    struct Input { T* feature; ProjectionInputs projected; ProjectionPlan plan; const FeatureMap* map; };
    std::vector<Input> inputs;
    auto project=[&](const FeatureMap& map) {
        auto plan=project_front_view(coords,grid_resolution,map.width,map.height,camera);
        auto* tensor=ggml_new_tensor_2d(g.ctx,GGML_TYPE_F32,map.channels,map.width*map.height); ggml_set_input(tensor);
        auto projected=build_projection(g.ctx,tensor,map.width,map.height,coords.size());
        inputs.push_back({tensor,projected,std::move(plan),&map}); return projected.result;
    };
    T* result=project(features.patches);
    if (high) result=ggml_concat(g.ctx,result,project(*high),0);
    g.allocate(backend,{result});
    for (const auto& input:inputs) { upload(input.feature,input.map->values); upload_projection(input.projected,input.plan); }
    g.compute(backend);
    auto projected=trellis::tensor_to_f32(result); finite(projected);
    ConditionPair conditions;
    conditions.positive={features.global,std::move(projected)};
    conditions.negative.global.resize(conditions.positive.global.size(),0.f);
    conditions.negative.projected.resize(conditions.positive.projected.size(),0.f);
    return conditions;
}

ConditionPair image_conditions_projected(ggml_backend* backend,const ImageFeatures& features,
                               const std::vector<std::array<int,3>>& coords,int grid,
                               const Camera& camera,const std::vector<float>& high) {
    if (features.patches.channels<1 || coords.empty() || coords.size()>1048576 ||
        high.size()!=coords.size()*size_t(features.patches.channels))
        throw std::invalid_argument("projected NAF feature extent mismatch");
    finite(high);
    auto result=image_conditions(backend,features,coords,grid,camera);
    const size_t channels=features.patches.channels;
    std::vector<float> combined(2*high.size());
    for (size_t i=0;i<coords.size();++i) {
        std::copy_n(result.positive.projected.begin()+i*channels,channels,combined.begin()+2*i*channels);
        std::copy_n(high.begin()+i*channels,channels,combined.begin()+(2*i+1)*channels);
    }
    result.positive.projected=std::move(combined);
    result.negative.projected.assign(result.positive.projected.size(),0.f);
    return result;
}
}
