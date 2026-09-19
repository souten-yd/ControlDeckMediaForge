// Sparse graph architecture adapted from pinned trellis.cpp and Pixal3D; ../NOTICE.
#include "sparse_decoder.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <unordered_map>

namespace mediaforge::pixal {
namespace {
using T=ggml_tensor;
void cancel(const SparseDecoderOptions& o) { if (o.cancelled && o.cancelled()) throw std::runtime_error("sparse decoder cancelled"); }
void finite(const std::vector<float>& v) { for (float x:v) if (!std::isfinite(x)) throw std::invalid_argument("non-finite sparse decoder value"); }
uint64_t key(int x,int y,int z) { return (uint64_t(x)<<42)|(uint64_t(y)<<21)|uint64_t(z); }
void validate(const SparseLatent& x,const SparseDecoderOptions& o) {
    if (x.coords.empty() || x.coords.size()>o.max_voxels || x.grid_resolution<2 || x.grid_resolution>4096 ||
        x.channels<1 || x.channels>16384 || x.values.size()!=x.coords.size()*size_t(x.channels)) throw std::invalid_argument("invalid sparse decoder input extent");
    std::unordered_map<uint64_t,int> seen;
    for (size_t i=0;i<x.coords.size();++i) {
        const auto& c=x.coords[i]; for (int v:c) if (v<0 || v>=x.grid_resolution) throw std::invalid_argument("sparse decoder coordinate outside grid");
        if (!seen.emplace(key(c[0],c[1],c[2]),int(i)).second) throw std::invalid_argument("duplicate sparse decoder coordinate");
    }
    finite(x.values);
}
std::vector<int32_t> neighbors(const Coordinates& coords,int grid,const SparseDecoderOptions& options) {
    int n=int(coords.size()); std::unordered_map<uint64_t,int> map; map.reserve(coords.size()*2);
    for (int i=0;i<n;++i) map.emplace(key(coords[i][0],coords[i][1],coords[i][2]),i);
    std::vector<int32_t> indices(size_t(n)*27,n);
    for (int i=0;i<n;++i) {
        if (i%4096==0) cancel(options);
        for (int dx=-1;dx<=1;++dx) for (int dy=-1;dy<=1;++dy) for (int dz=-1;dz<=1;++dz) {
            int x=coords[i][0]+dx,y=coords[i][1]+dy,z=coords[i][2]+dz;
            if (x<0 || y<0 || z<0 || x>=grid || y>=grid || z>=grid) continue;
            auto found=map.find(key(x,y,z));
            if (found!=map.end()) indices[size_t(i)*27+(dx+1)*9+(dy+1)*3+dz+1]=found->second;
        }
    }
    return indices;
}
struct Graph {
    ggml_context* ctx=nullptr; ggml_gallocr_t allocator=nullptr;
    Graph() { ctx=ggml_init({ggml_tensor_overhead()*8192+ggml_graph_overhead_custom(8192,false)+(1<<20),nullptr,true}); if (!ctx) throw std::runtime_error("sparse graph context failed"); }
    ~Graph() { if (allocator) ggml_gallocr_free(allocator); if (ctx) ggml_free(ctx); }
};
struct Buffer {
    ggml_context* ctx=nullptr; ggml_backend_buffer_t buffer=nullptr; T* tensor=nullptr;
    ~Buffer() { if (buffer) ggml_backend_buffer_free(buffer); if (ctx) ggml_free(ctx); }
};
std::unique_ptr<Buffer> hold(const trellis::Model& model,const std::vector<float>& values,int channels,bool pad,SparseDecoderStats& stats) {
    auto b=std::make_unique<Buffer>();
    b->ctx=ggml_init({ggml_tensor_overhead()*4+4096,nullptr,true});
    if (!b->ctx) throw std::runtime_error("sparse input context failed");
    b->tensor=ggml_new_tensor_2d(b->ctx,GGML_TYPE_F32,channels,int64_t(values.size()/channels)+(pad?1:0)); ggml_set_input(b->tensor);
    b->buffer=ggml_backend_alloc_ctx_tensors(b->ctx,model.backend);
    if (!b->buffer) throw std::runtime_error("sparse input allocation failed");
    ggml_backend_tensor_set(b->tensor,values.data(),0,values.size()*sizeof(float));
    if (pad) { std::vector<float> zero(channels,0); ggml_backend_tensor_set(b->tensor,zero.data(),values.size()*sizeof(float),zero.size()*sizeof(float)); }
    stats.input_buffer_max_bytes=std::max(stats.input_buffer_max_bytes,ggml_backend_buffer_get_size(b->buffer));
    return b;
}
T* weight(ggml_context* c,const trellis::Model& m,const std::string& name) {
    T* t=m.get(name); return t->type==GGML_TYPE_F32?t:ggml_cast(c,t,GGML_TYPE_F32);
}
T* linear(ggml_context* c,const trellis::Model& m,const std::string& name,T* x) {
    return ggml_add(c,ggml_mul_mat(c,weight(c,m,name+".weight"),x),weight(c,m,name+".bias"));
}
T* norm(ggml_context* c,const trellis::Model& m,const std::string& name,T* x,float epsilon) {
    x=ggml_norm(c,x,epsilon);
    if (!name.empty()) x=ggml_add(c,ggml_mul(c,x,weight(c,m,name+".weight")),weight(c,m,name+".bias"));
    return x;
}
std::vector<float> compute(Graph& graph,const trellis::Model& model,T* output,const std::vector<std::pair<T*,const void*>>& inputs,
    const SparseDecoderOptions& options,SparseDecoderStats& stats) {
    cancel(options); auto* g=ggml_new_graph_custom(graph.ctx,8192,false); ggml_set_output(output);
    for (auto* p=output->view_src;p;p=p->view_src) ggml_set_output(p);
    ggml_build_forward_expand(g,output);
    for (int i=0;i<ggml_graph_n_nodes(g);++i) {
        auto* t=ggml_graph_node(g,i);
        if (!ggml_backend_dev_supports_op(ggml_backend_get_device(model.backend),t)) throw std::runtime_error(std::string("selected backend cannot execute sparse decoder op: ")+ggml_op_name(t->op));
    }
    graph.allocator=ggml_gallocr_new(ggml_backend_get_default_buffer_type(model.backend));
    if (!graph.allocator || !ggml_gallocr_alloc_graph(graph.allocator,g)) throw std::runtime_error("sparse graph allocation failed");
    stats.graph_peak_bytes=std::max(stats.graph_peak_bytes,ggml_gallocr_get_buffer_size(graph.allocator,0));
    for (const auto& [t,data]:inputs) ggml_backend_tensor_set(t,data,0,ggml_nbytes(t));
    cancel(options);
    if (ggml_backend_graph_compute(model.backend,g)!=GGML_STATUS_SUCCESS) throw std::runtime_error("sparse graph compute failed");
    ++stats.graph_executions; cancel(options);
    auto out=trellis::tensor_to_f32(output); finite(out); return out;
}
// Linear or normalization work is per row and needs no entire-grid allocation.
std::vector<float> rows(const trellis::Model& m,const std::vector<float>& data,int ci,int co,const std::string& name,
    bool normalization,bool activation,float epsilon,const SparseDecoderOptions& o,SparseDecoderStats& stats) {
    int n=int(data.size()/ci); std::vector<float> result(size_t(n)*co);
    for (int first=0;first<n;first+=o.chunk_rows) {
        int count=std::min(o.chunk_rows,n-first); Graph graph; auto* c=graph.ctx;
        T* input=ggml_new_tensor_2d(c,GGML_TYPE_F32,ci,count); ggml_set_input(input);
        T* h=normalization?norm(c,m,name,input,epsilon):linear(c,m,name,input);
        if (activation) h=ggml_silu(c,h);
        auto out=compute(graph,m,h,{{input,data.data()+size_t(first)*ci}},o,stats);
        std::copy(out.begin(),out.end(),result.begin()+size_t(first)*co);
    }
    return result;
}
struct Children { Coordinates coords; std::vector<int32_t> indices,starts; };
Children children(const Coordinates& coords,const std::vector<float>& logits,const SparseDecoderOptions& o) {
    finite(logits);
    if (logits.size()!=coords.size()*8) throw std::invalid_argument("invalid subdivision logits extent");
    Children result; result.starts.reserve(coords.size()+1);
    for (size_t i=0;i<coords.size();++i) {
        if (i%4096==0) cancel(o);
        result.starts.push_back(int32_t(result.coords.size()));
        for (int s=0;s<8;++s) if (logits[i*8+s]>0) {
            if (result.coords.size()>=o.max_voxels) throw std::invalid_argument("sparse subdivision exceeds explicit voxel budget");
            result.coords.push_back({coords[i][0]*2+(s&1),coords[i][1]*2+((s>>1)&1),coords[i][2]*2+((s>>2)&1)});
            result.indices.push_back(int32_t(i*8+s));
        }
    }
    result.starts.push_back(int32_t(result.coords.size()));
    if (result.coords.empty()) throw std::runtime_error("sparse subdivision has no active voxels");
    return result;
}
enum class ConvMode { Next, Expand, Skip };
std::vector<float> convolution(const trellis::Model& m,const std::string& name,const std::vector<float>& data,int ci,int co,
    const std::vector<int32_t>& neighbors,const SparseDecoderOptions& options,SparseDecoderStats& stats,ConvMode mode,
    const Children* plan=nullptr,const Buffer* skip=nullptr) {
    int n=int(data.size()/ci); auto held=hold(m,data,ci,true,stats);
    const bool expand=mode==ConvMode::Expand;
    const size_t result_rows=expand?plan->coords.size():size_t(n); const int result_channels=expand?co/8:co;
    std::vector<float> result(result_rows*result_channels);
    for (int first=0;first<n;first+=options.chunk_rows) {
        cancel(options); int count=std::min(options.chunk_rows,n-first);
        int out_first=expand?plan->starts[first]:first,out_count=expand?plan->starts[first+count]-out_first:count;
        if (!out_count) continue;
        Graph graph; auto* c=graph.ctx;
        T* ids=ggml_new_tensor_1d(c,GGML_TYPE_I32,int64_t(count)*27); ggml_set_input(ids);
        T* patch=ggml_reshape_2d(c,ggml_get_rows(c,held->tensor,ids),int64_t(ci)*27,count);
        auto prefix=name+(mode==ConvMode::Next?".conv":"");
        T* w=ggml_reshape_2d(c,weight(c,m,prefix+".weight"),int64_t(ci)*27,co);
        T* h=ggml_add(c,ggml_mul_mat(c,w,patch),weight(c,m,prefix+".bias"));
        std::vector<std::pair<T*,const void*>> uploads{{ids,neighbors.data()+size_t(first)*27}};
        std::vector<int32_t> select(out_count);
        T* indices=ggml_new_tensor_1d(c,GGML_TYPE_I32,out_count); ggml_set_input(indices);
        if (mode==ConvMode::Next) {
            h=norm(c,m,name+".norm",h,1e-6f); h=linear(c,m,name+".mlp.0",h); h=ggml_silu(c,h); h=linear(c,m,name+".mlp.2",h);
            std::iota(select.begin(),select.end(),first);
            h=ggml_add(c,h,ggml_get_rows(c,held->tensor,indices));
        } else if (expand) {
            for (int i=0;i<out_count;++i) select[i]=plan->indices[out_first+i]-first*8;
            h=ggml_get_rows(c,ggml_reshape_2d(c,h,co/8,int64_t(count)*8),indices);
        } else {
            std::copy_n(plan->indices.begin()+first,count,select.begin());
            int k=int(skip->tensor->ne[0])/8,repeat=co/k;
            T* base=ggml_get_rows(c,ggml_reshape_2d(c,skip->tensor,k,skip->tensor->ne[1]*8),indices);
            T* residual=ggml_repeat_4d(c,ggml_reshape_3d(c,base,1,k,count),repeat,k,count,1);
            h=ggml_add(c,h,ggml_reshape_2d(c,residual,co,count));
        }
        uploads.emplace_back(indices,select.data());
        auto out=compute(graph,m,h,uploads,options,stats);
        std::copy(out.begin(),out.end(),result.begin()+size_t(out_first)*result_channels);
    }
    return result;
}
SparseDecodeResult execute(const SparseDecoderModel& model,const SparseLatent& latent,const std::vector<Subdivision>* guides,
    const SparseDecoderOptions& options,SparseDecoderStats* stats,std::map<std::string,std::vector<float>>* debug,int stop) {
    const auto& p=model.spec().params; const auto& m=model.weights();
    if (!m.backend || options.chunk_rows<1 || options.chunk_rows>65536 || options.max_voxels<1 || options.max_voxels>64*1024*1024 ||
        (p.reference_fp16 && !options.f32_arithmetic)) throw std::invalid_argument("invalid sparse decoder options or missing explicit F32 evaluation");
    validate(latent,options);
    if (latent.channels!=p.latent_channels || latent.grid_resolution>4096/(1<<(p.channels.size()-1)) ||
        (p.kind=="shape" && guides) || (p.kind=="texture" && (!guides || guides->size()+1!=p.channels.size())))
        throw std::invalid_argument("sparse decoder latent/guide/grid mismatch");
    if (stop>=int(p.channels.size()) || stop<-1 || (stop>=0 && p.kind!="shape")) throw std::invalid_argument("invalid shape upsample count");
    cancel(options); SparseDecoderStats measured; std::map<std::string,std::vector<float>> observed;
    SparseDecodeResult result; auto& x=result.fields; x.coords=latent.coords; x.grid_resolution=latent.grid_resolution; x.channels=p.channels[0];
    x.values=rows(m,latent.values,latent.channels,x.channels,"from_latent",false,false,0,options,measured);
    if (debug) observed["from_latent"]=x.values;
    const int total=stop>=0?stop:int(p.channels.size()); if (options.progress) options.progress(0,total);
    for (int stage=0;stage<int(p.channels.size());++stage) {
        if (stage==stop) break;
        cancel(options); auto neighbor=neighbors(x.coords,x.grid_resolution,options);
        for (int j=0;j<p.blocks[stage];++j) {
            auto prefix="blocks."+std::to_string(stage)+"."+std::to_string(j);
            x.values=convolution(m,prefix,x.values,x.channels,x.channels,neighbor,options,measured,ConvMode::Next);
            if (debug) observed[prefix]=x.values;
        }
        if (stage+1<int(p.channels.size())) {
            auto prefix="blocks."+std::to_string(stage)+"."+std::to_string(p.blocks[stage]);
            std::vector<float> logits;
            if (p.kind=="shape") logits=rows(m,x.values,x.channels,8,prefix+".to_subdiv",false,false,0,options,measured);
            else {
                const auto& guide=guides->at(stage);
                if (guide.grid_resolution!=x.grid_resolution || guide.coords!=x.coords) throw std::invalid_argument("texture subdivision guide coordinate/order mismatch");
                logits=guide.logits;
            }
            auto plan=children(x.coords,logits,options);
            if (p.kind=="shape") result.subdivisions.push_back({x.coords,x.grid_resolution,logits});
            if (debug) observed[prefix+".subdiv"]=logits;
            auto normalized=rows(m,x.values,x.channels,x.channels,prefix+".norm1",true,true,1e-6f,options,measured);
            int out_channels=p.channels[stage+1];
            auto expanded=convolution(m,prefix+".conv1",normalized,x.channels,out_channels*8,neighbor,options,measured,ConvMode::Expand,&plan);
            normalized.clear(); normalized.shrink_to_fit();
            if (debug) observed[prefix+".expanded"]=expanded;
            auto next=rows(m,expanded,out_channels,out_channels,"",true,true,1e-6f,options,measured);
            expanded.clear(); expanded.shrink_to_fit();
            auto next_neighbors=neighbors(plan.coords,x.grid_resolution*2,options);
            auto skip=hold(m,x.values,x.channels,false,measured);
            x.values=convolution(m,prefix+".conv2",next,out_channels,out_channels,next_neighbors,options,measured,ConvMode::Skip,&plan,skip.get());
            x.coords=std::move(plan.coords); x.grid_resolution*=2; x.channels=out_channels;
            if (debug) observed[prefix]=x.values;
        }
        if (options.progress) options.progress(stage+1,total);
    }
    if (stop<0) {
        x.values=rows(m,x.values,x.channels,x.channels,"",true,false,1e-5f,options,measured);
        if (debug) observed["final_norm"]=x.values;
        x.values=rows(m,x.values,x.channels,p.out_channels,"output_layer",false,false,0,options,measured); x.channels=p.out_channels;
        if (debug) observed["output_layer"]=x.values;
    }
    cancel(options); if (stats) *stats=measured; if (debug) *debug=std::move(observed); return result;
}
}
SparseDecodeResult decode_sparse(const SparseDecoderModel& model,const SparseLatent& latent,const std::vector<Subdivision>* guides,
    const SparseDecoderOptions& options,SparseDecoderStats* stats,std::map<std::string,std::vector<float>>* debug) {
    return execute(model,latent,guides,options,stats,debug,-1);
}
Coordinates upsample_shape(const SparseDecoderModel& model,const SparseLatent& latent,int times,const SparseDecoderOptions& options,SparseDecoderStats* stats) {
    if (times<0) throw std::invalid_argument("negative shape upsample count");
    return execute(model,latent,nullptr,options,stats,nullptr,times).fields.coords;
}
}
