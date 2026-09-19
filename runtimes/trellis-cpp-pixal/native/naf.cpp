// NAF encoder and local attention port; see ../NOTICE for attribution.
// RoPE uses the half-rotation GGML construction from image_features.cpp.
#include "naf.h"
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-alloc.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mediaforge::pixal {
namespace {
using T=ggml_tensor;
void finite(const std::vector<float>& v) {
    for (float x:v) if (!std::isfinite(x)) throw std::invalid_argument("non-finite NAF tensor");
}
void check_cancel(const std::function<bool()>& cancelled) {
    if (cancelled && cancelled()) throw std::runtime_error("NAF cancelled");
}
struct Graph {
    ggml_context* ctx=ggml_init({ggml_tensor_overhead()*8192+ggml_graph_overhead_custom(8192,false)+(1<<20),nullptr,true});
    ggml_cgraph* graph=nullptr;
    ggml_gallocr_t allocator=nullptr;
    std::vector<std::pair<T*,std::vector<float>>> floats;
    std::vector<std::pair<T*,std::vector<int32_t>>> indices;
    Graph() { if (!ctx) throw std::runtime_error("NAF graph metadata allocation failed"); }
    ~Graph() { if (allocator) ggml_gallocr_free(allocator); ggml_free(ctx); }
    T* input(int64_t a,int64_t b,const std::vector<float>& values) {
        T* t=ggml_new_tensor_2d(ctx,GGML_TYPE_F32,a,b); ggml_set_input(t);
        if (size_t(a*b)!=values.size()) throw std::invalid_argument("NAF internal input shape mismatch");
        floats.emplace_back(t,values); return t;
    }
    T* index(const std::vector<int32_t>& values) {
        T* t=ggml_new_tensor_1d(ctx,GGML_TYPE_I32,values.size()); ggml_set_input(t);
        indices.emplace_back(t,values); return t;
    }
    size_t allocate(ggml_backend* backend,const std::vector<T*>& outputs) {
        graph=ggml_new_graph_custom(ctx,8192,false);
        for (T* t:outputs) {
            ggml_set_output(t);
            // GGML output flags on a reshape/view do not protect its owning
            // tensor from in-place reuse by a later dependent operation.
            for (T* owner=t->view_src;owner;owner=owner->view_src) ggml_set_output(owner);
            ggml_build_forward_expand(graph,t);
        }
        for (int i=0;i<ggml_graph_n_nodes(graph);++i) {
            T* t=ggml_graph_node(graph,i);
            if (!ggml_backend_dev_supports_op(ggml_backend_get_device(backend),t))
                throw std::runtime_error(std::string("selected backend cannot execute NAF operation: ")+ggml_op_name(t->op));
        }
        allocator=ggml_gallocr_new(ggml_backend_get_default_buffer_type(backend));
        if (!allocator || !ggml_gallocr_alloc_graph(allocator,graph)) throw std::runtime_error("NAF graph allocation failed");
        return ggml_gallocr_get_buffer_size(allocator,0);
    }
    void compute(ggml_backend* backend,const std::function<bool()>& cancelled,bool upload_floats=true,
                 const std::function<void()>& extra_upload={}) {
        check_cancel(cancelled);
        // Inputs may share allocator storage. Re-upload every execution.
        if (upload_floats) for (const auto& [t,v]:floats) ggml_backend_tensor_set(t,v.data(),0,v.size()*sizeof(float));
        for (const auto& [t,v]:indices) ggml_backend_tensor_set(t,v.data(),0,v.size()*sizeof(int32_t));
        if (extra_upload) extra_upload();
        if (ggml_backend_graph_compute(backend,graph)!=GGML_STATUS_SUCCESS) throw std::runtime_error("NAF graph compute failed");
        check_cancel(cancelled);
    }
};
T* spatial(Graph& g,T* hwc,int width,int height,int channels) {
    return ggml_cont(g.ctx,ggml_permute(g.ctx,ggml_reshape_3d(g.ctx,hwc,channels,width,height),2,0,1,3));
}
T* pixel(Graph& g,T* chw) {
    return ggml_reshape_2d(g.ctx,ggml_cont(g.ctx,ggml_permute(g.ctx,chw,1,2,0,3)),chw->ne[2],chw->ne[0]*chw->ne[1]);
}
// Separable exact adaptive-average bins, including overlapping/non-divisible
// bins and output larger than input. Regular divisible bins use native pooling.
T* average(Graph& g,T* x,int width,int height) {
    const int iw=x->ne[0],ih=x->ne[1],ch=x->ne[2]; auto* c=g.ctx;
    if (iw==width && ih==height) return x;
    if (iw%width==0 && ih%height==0)
        return ggml_pool_2d(c,x,GGML_OP_POOL_AVG,iw/width,ih/height,iw/width,ih/height,0,0);
    auto bins=[&](int in,int out) {
        std::vector<float> weights(size_t(in)*out,0.f);
        for (int o=0;o<out;++o) {
            int first=o*in/out,last=((o+1)*in+out-1)/out;
            for (int j=first;j<last;++j) weights[size_t(o)*in+j]=1.f/(last-first);
        }
        return g.input(in,out,weights);
    };
    T* y=ggml_mul_mat(c,bins(iw,width),ggml_reshape_2d(c,x,iw,ih*ch));
    y=ggml_cont(c,ggml_permute(c,ggml_reshape_3d(c,y,width,ih,ch),1,0,2,3));
    y=ggml_mul_mat(c,bins(ih,height),ggml_reshape_2d(c,y,ih,width*ch));
    return ggml_cont(c,ggml_permute(c,ggml_reshape_3d(c,y,height,width,ch),1,0,2,3));
}
int nearest(int coordinate,int low,int high) {
    return std::min(low-1,int((int64_t(2)*coordinate+1)*low/(int64_t(2)*high)));
}
// The neighborhood shifts at borders, retaining exactly K members in the
// query's dilation residue class. This is not zero or repeated-edge padding.
int window_start(int coordinate,int size,int dilation,int kernel) {
    const int residue=coordinate%dilation;
    const int count=(size-1-residue)/dilation+1;
    return residue+dilation*std::clamp(coordinate/dilation-kernel/2,0,count-kernel);
}

std::vector<float> evaluate_naf(const trellis::Model& model,const NafParams& p,
                        const std::vector<float>& rgb,int iw,int ih,const FeatureMap& low,int ow,int oh,
                        NafStats* stats,std::map<std::string,std::vector<float>>* debug,
                        const std::function<bool()>& cancelled,const ProjectionPlan* projection) {
    const size_t rows=projection ? projection->indices[0].size() : size_t(std::max(ow,0))*std::max(oh,0);
    if (!model.backend || p.channels<16 || p.channels>512 || p.channels%16 ||
        p.heads<1 || p.heads>16 || p.channels%p.heads || p.rope_heads<1 || p.rope_heads>16 ||
        p.channels%(4*p.rope_heads) || p.layers<0 || p.layers>4 || p.kernel<3 || p.kernel>15 || p.kernel%2==0 ||
        p.tile_pixels<1 || p.tile_pixels>512 || iw<2 || ih<2 || iw>2048 || ih>2048 ||
        ow<1 || oh<1 || ow>1024 || oh>1024 || low.width<1 || low.height<1 || low.width>ow || low.height>oh ||
        low.channels<1 || low.channels>4096 || low.channels%p.heads ||
        rgb.size()!=size_t(3)*iw*ih || low.values.size()!=size_t(low.channels)*low.width*low.height ||
        rows<1 || rows>1048576 || size_t(low.channels)*rows>size_t(512)*1024*1024)
        throw std::invalid_argument("invalid NAF configuration/input dimensions");
    const int dx=ow/low.width,dy=oh/low.height;
    if (ow/dx<p.kernel || oh/dy<p.kernel) throw std::invalid_argument("NAF neighborhood exceeds dilated feature extent");
    finite(rgb); finite(low.values);
    for (float x:rgb) if (x<0 || x>1) throw std::invalid_argument("NAF RGB must be in [0,1]");
    check_cancel(cancelled);
    NafStats measured;
    const int D=p.channels,HD=D/p.heads,RD=D/p.rope_heads,C=low.channels,N=ow*oh,LR=low.width*low.height;
    std::vector<float> query,key;
    // Encoder and attention graphs have disjoint lifetimes to release large
    // convolution intermediates before gathering any attention neighborhoods.
    {
        Graph g; auto* c=g.ctx;
        std::map<std::string,T*> observed;
        auto keep=[&](const std::string& name,T* t) { if (debug) observed[name]=t; return t; };
        auto weight=[&](const std::string& name,std::initializer_list<int64_t> shape) {
            T* t=model.get(name); int axis=0;
            if (t->type!=GGML_TYPE_F32 && t->type!=GGML_TYPE_F16) throw std::invalid_argument("unsupported NAF weight type: "+name);
            for (int64_t dim:shape) if (t->ne[axis++]!=dim) throw std::invalid_argument("NAF weight shape mismatch: "+name);
            for (;axis<GGML_MAX_DIMS;++axis) if (t->ne[axis]!=1) throw std::invalid_argument("NAF weight rank mismatch: "+name);
            return p.f32_weight_arithmetic && t->type!=GGML_TYPE_F32 ? ggml_cast(c,t,GGML_TYPE_F32) : t;
        };
        auto conv=[&](T* x,const std::string& name,int out,int kernel) {
            const int w=x->ne[0],h=x->ne[1],in=x->ne[2];
            T* weights=weight(name+".weight",{kernel,kernel,in,out});
            if (kernel==3) {
                std::vector<int32_t> reflected(size_t(w+2)*(h+2));
                for (int y=0;y<h+2;++y) for (int j=0;j<w+2;++j) {
                    int yy=y==0 ? 1 : y==h+1 ? h-2 : y-1;
                    int xx=j==0 ? 1 : j==w+1 ? w-2 : j-1;
                    reflected[size_t(y)*(w+2)+j]=yy*w+xx;
                }
                x=spatial(g,ggml_get_rows(c,pixel(g,x),g.index(reflected)),w+2,h+2,in);
            }
            T* y=ggml_conv_2d(c,weights,x,1,1,0,0,1,1);
            return ggml_add(c,y,ggml_reshape_3d(c,weight(name+".bias",{out}),1,1,out));
        };
        auto norm=[&](T* x,const std::string& name) {
            int channels=x->ne[2]; T* y=ggml_group_norm(c,x,8,1e-5f);
            y=ggml_mul(c,y,ggml_reshape_3d(c,weight(name+".weight",{channels}),1,1,channels));
            return ggml_add(c,y,ggml_reshape_3d(c,weight(name+".bias",{channels}),1,1,channels));
        };
        T* guide=ggml_reshape_3d(c,g.input(iw*ih,3,rgb),iw,ih,3);
        if (ih>4*oh || iw>4*ow) {
            int h=std::min({ih,4*oh,4*ow}),w=std::min({iw,4*ow,4*oh});
            guide=ggml_interpolate(c,guide,w,h,3,1,GGML_SCALE_MODE_BILINEAR);
        }
        measured.guide_width=guide->ne[0]; measured.guide_height=guide->ne[1];
        keep("guide",guide);
        auto encode=[&](const std::string& branch,int kernel) {
            T* x=keep(branch+".0",conv(guide,"image_encoder."+branch+".0",D/2,kernel));
            for (int i=1;i<=p.layers;++i) {
                std::string b="image_encoder."+branch+"."+std::to_string(i);
                x=conv(ggml_silu(c,norm(x,b+".norm1")),b+".conv1",D/2,kernel);
                x=conv(ggml_silu(c,norm(x,b+".norm2")),b+".conv2",D/2,kernel);
                keep(branch+"."+std::to_string(i),x);
            }
            return x;
        };
        T* a=encode("encoder",1); T* b=encode("sem_encoder",3);
        T* pooled=keep("pooled",average(g,ggml_concat(c,a,b,2),ow,oh));
        T* x=ggml_reshape_3d(c,pixel(g,pooled),RD,p.rope_heads,N);
        // The persistent periods buffer belongs to the checkpoint, not to
        // runtime defaults. Coordinate trigonometry is host-side planning.
        T* periods=weight("image_encoder.rope.periods",{RD/4});
        // Cast tensors are graph expressions; read the original stored buffer.
        (void)periods;
        auto pv=trellis::tensor_to_f32(model.get("image_encoder.rope.periods")); finite(pv);
        for (float v:pv) if (v<=0) throw std::invalid_argument("NAF RoPE periods must be positive");
        std::vector<float> cosines(size_t(N)*RD),sines(cosines.size());
        for (int t=0;t<N;++t) for (int d=0;d<RD;++d) {
            int f=d%(RD/2),axis=f/(RD/4); float coord=axis==0 ? (t/ow+.5f)/oh : (t%ow+.5f)/ow;
            float angle=(6.283185307179586f*(2.f*coord-1.f))/pv[f%(RD/4)];
            cosines[size_t(t)*RD+d]=std::cos(angle); sines[size_t(t)*RD+d]=std::sin(angle);
        }
        T* cs=ggml_reshape_3d(c,g.input(RD,N,cosines),RD,1,N);
        T* sn=ggml_reshape_3d(c,g.input(RD,N,sines),RD,1,N);
        T* left=ggml_cont(c,ggml_view_3d(c,x,RD/2,p.rope_heads,N,x->nb[1],x->nb[2],0));
        T* right=ggml_cont(c,ggml_view_3d(c,x,RD/2,p.rope_heads,N,x->nb[1],x->nb[2],RD/2*x->nb[0]));
        T* rotated=ggml_add(c,ggml_mul(c,x,cs),ggml_mul(c,ggml_concat(c,ggml_scale(c,right,-1.f),left,0),sn));
        T* q=keep("query",ggml_reshape_2d(c,rotated,D,N));
        T* k=keep("key",pixel(g,average(g,spatial(g,q,ow,oh,D),low.width,low.height)));
        std::vector<T*> outputs{q,k}; for (const auto& [name,t]:observed) outputs.push_back(t);
        measured.encoder_graph_bytes=g.allocate(model.backend,outputs); g.compute(model.backend,cancelled);
        query=trellis::tensor_to_f32(q); key=trellis::tensor_to_f32(k); finite(query); finite(key);
        if (debug) for (const auto& [name,t]:observed) (*debug)[name]=trellis::tensor_to_f32(t);
    }
    std::vector<float> output(size_t(C)*rows);
    measured.output_bytes=output.size()*sizeof(float);
    measured.dense_output_bytes=size_t(C)*N*sizeof(float);
    measured.attention_queries=rows*(projection ? 4 : 1);
    {
        Graph g; auto* c=g.ctx;
        const int tile_rows=std::min(rows,size_t(projection ? std::max(1,p.tile_pixels/4) : p.tile_pixels));
        const int B=tile_rows*(projection ? 4 : 1),K=p.kernel*p.kernel,VD=C/p.heads;
        T* q=g.input(D,N,query),*k=g.input(D,LR,key),*v=g.input(C,LR,low.values);
        T* qi=g.index(std::vector<int32_t>(B)),*ki=g.index(std::vector<int32_t>(size_t(K)*B));
        T* qt=ggml_reshape_4d(c,ggml_get_rows(c,q,qi),HD,p.heads,1,B);
        qt=ggml_cont(c,ggml_permute(c,qt,0,2,1,3));
        T* kt=ggml_reshape_4d(c,ggml_get_rows(c,k,ki),HD,p.heads,K,B);
        kt=ggml_cont(c,ggml_permute(c,kt,0,2,1,3));
        T* attention=ggml_soft_max_ext(c,ggml_mul_mat(c,kt,qt),nullptr,1.f/std::sqrt(float(HD)),0.f);
        T* vt=ggml_reshape_4d(c,ggml_get_rows(c,v,ki),VD,p.heads,K,B);
        vt=ggml_cont(c,ggml_permute(c,vt,1,2,0,3));
        T* result=ggml_reshape_2d(c,ggml_cont(c,ggml_mul_mat(c,vt,attention)),C,B);
        ProjectionInputs reduced{};
        ProjectionPlan tile_plan{B,1,{},{}};
        if (projection) {
            reduced=build_projection(c,result,B,1,tile_rows); result=reduced.result;
            for (int corner=0;corner<4;++corner) {
                tile_plan.indices[corner].resize(tile_rows); tile_plan.weights[corner].resize(tile_rows);
                for (int t=0;t<tile_rows;++t) tile_plan.indices[corner][t]=4*t+corner;
            }
        }
        // Graph owns the upload copies; release the encoder readback copies.
        std::vector<float>().swap(query); std::vector<float>().swap(key);
        // Retain Q/K/V buffers across tiles so they are uploaded only once.
        measured.attention_graph_bytes=g.allocate(model.backend,{result,q,k,v});
        for (size_t start=0;start<rows;start+=tile_rows) {
            check_cancel(cancelled);
            auto& qindex=g.indices[0].second; auto& kindex=g.indices[1].second;
            for (int t=0;t<B;++t) {
                size_t row=std::min(start+(projection ? t/4 : t),rows-1);
                int pos=projection ? projection->indices[t%4][row] : int(row); qindex[t]=pos;
                if (projection) tile_plan.weights[t%4][t/4]=projection->weights[t%4][row];
                int x=pos%ow,y=pos/ow,x0=window_start(x,ow,dx,p.kernel),y0=window_start(y,oh,dy,p.kernel);
                for (int ky=0;ky<p.kernel;++ky) for (int kx=0;kx<p.kernel;++kx)
                    kindex[size_t(t)*K+ky*p.kernel+kx]=nearest(y0+ky*dy,low.height,oh)*low.width+nearest(x0+kx*dx,low.width,ow);
            }
            g.compute(model.backend,cancelled,start==0,[&]() { if (projection) upload_projection(reduced,tile_plan); }); auto tile=trellis::tensor_to_f32(result); finite(tile);
            std::copy_n(tile.begin(),std::min(size_t(tile_rows),rows-start)*C,output.begin()+start*C);
            ++measured.tiles;
        }
    }
    if (stats) *stats=measured;
    return output;
}
} // namespace

FeatureMap upsample_naf(const trellis::Model& model,const NafParams& p,
                        const std::vector<float>& rgb,int iw,int ih,const FeatureMap& low,int ow,int oh,
                        NafStats* stats,std::map<std::string,std::vector<float>>* debug,
                        const std::function<bool()>& cancelled) {
    return {low.channels,ow,oh,evaluate_naf(model,p,rgb,iw,ih,low,ow,oh,stats,debug,cancelled,nullptr)};
}
std::vector<float> project_naf(const trellis::Model& model,const NafParams& p,
                        const std::vector<float>& rgb,int iw,int ih,const FeatureMap& low,int ow,int oh,
                        const std::vector<std::array<int,3>>& coords,int grid,const Camera& camera,
                        NafStats* stats,std::map<std::string,std::vector<float>>* debug,
                        const std::function<bool()>& cancelled) {
    check_cancel(cancelled);
    if (coords.empty() || coords.size()>1048576 || ow<1 || oh<1 || ow>1024 || oh>1024)
        throw std::invalid_argument("invalid projected NAF extent");
    auto plan=project_front_view(coords,grid,ow,oh,camera);
    return evaluate_naf(model,p,rgb,iw,ih,low,ow,oh,stats,debug,cancelled,&plan);
}
}
