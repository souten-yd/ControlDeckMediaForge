// Private production entry. The parent owns file admission and genuine lease.
#include "pipeline.h"
#include "bounded_npy.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include <algorithm>
#include <charconv>
#include <csignal>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sys/stat.h>
namespace pixal=mediaforge::pixal;
namespace fs=std::filesystem;
namespace trellis { extern bool g_no_fa; }
namespace {
volatile std::sig_atomic_t interrupted=0;
void request_stop(int) { interrupted=1; }
uint32_t number(const std::string& text,uint32_t maximum) {
    uint32_t result=0;auto parsed=std::from_chars(text.data(),text.data()+text.size(),result);
    if (text.empty() || parsed.ec!=std::errc() || parsed.ptr!=text.data()+text.size() || result>maximum)
        throw std::invalid_argument("invalid integer worker argument");
    return result;
}
bool digest(const std::string& value) {
    return value.size()==64 && std::all_of(value.begin(),value.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
}
int main(int argc,char** argv) {
    fs::path owned;
    try {
        std::signal(SIGTERM,request_stop);std::signal(SIGINT,request_stop);
        if (argc<2) throw std::invalid_argument("mode must be inspect or generate");
        std::string mode=argv[1];bool inspect=mode=="inspect";
        if (!inspect && mode!="generate") throw std::invalid_argument("invalid worker mode");
        const std::set<std::string> model_flags={"--dino","--naf","--ss-flow","--ss-decoder","--shape-lr","--shape-hr","--shape-decoder","--texture-flow","--texture-decoder","--source-kind"};
        std::set<std::string> required=model_flags;
        if (!inspect) for (const auto* key:{"--input","--output","--backend","--precision","--source-sha","--input-sha","--seed","--resolution","--max-tokens","--naf-lr","--naf-hr","--naf-texture","--texture-size","--target-faces","--decoder-chunk","--max-voxels","--max-triangles"}) required.insert(key);
        auto allowed=required;if (!inspect) allowed.insert("--device");
        std::map<std::string,std::string> flags;
        for (int i=2;i<argc;i+=2) {
            if (i+1>=argc || !allowed.count(argv[i]) || flags.count(argv[i])) throw std::invalid_argument("unknown, repeated or incomplete worker argument");
            flags[argv[i]]=argv[i+1];
        }
        for (const auto& key:required) if (!flags.count(key)) throw std::invalid_argument("missing worker argument: "+key);
        pixal::PipelineModels models{flags.at("--dino"),flags.at("--naf"),flags.at("--ss-flow"),flags.at("--ss-decoder"),flags.at("--shape-lr"),flags.at("--shape-hr"),flags.at("--shape-decoder"),flags.at("--texture-flow"),flags.at("--texture-decoder")};
        const auto source_kind=pixal::inspect_pipeline(models);
        if (source_kind!=flags.at("--source-kind")) throw std::invalid_argument("worker checkpoint source kind differs");
        if (interrupted) throw std::runtime_error("Pixal worker cancelled");
        if (inspect) {std::cout << "{\"valid\":true,\"source_kind\":\"" << source_kind << "\"}\n";return 0;}
        const std::string kind=flags.at("--backend");const bool gpu=kind=="vulkan";
        if ((kind!="cpu" && !gpu) || gpu!=bool(flags.count("--device")) || flags.at("--precision")!="float32")
            throw std::invalid_argument("explicit backend/device/float32 required");
        int device=gpu?int(number(flags.at("--device"),31)):-1;
        for (const auto* key:{"--source-sha","--input-sha"}) if (!digest(flags.at(key))) throw std::invalid_argument("invalid provenance digest");
        pixal::PipelineOptions options;options.f32_arithmetic=true;
        options.seed=number(flags.at("--seed"),2147483647);options.resolution=number(flags.at("--resolution"),1536);
        options.max_tokens=number(flags.at("--max-tokens"),1048576);
        options.naf_lr=number(flags.at("--naf-lr"),1024);options.naf_hr=number(flags.at("--naf-hr"),1024);options.naf_texture=number(flags.at("--naf-texture"),1024);
        options.surface.texture_size=number(flags.at("--texture-size"),4096);options.surface.target_faces=number(flags.at("--target-faces"),5000000);
        options.decoder.chunk_rows=number(flags.at("--decoder-chunk"),65536);options.decoder.max_voxels=number(flags.at("--max-voxels"),64*1024*1024);
        options.mesh.max_voxels=options.decoder.max_voxels;options.mesh.max_triangles=number(flags.at("--max-triangles"),256*1024*1024);
        if ((options.resolution!=1024 && options.resolution!=1536) || !options.max_tokens || !options.naf_lr || !options.naf_hr || !options.naf_texture ||
            options.surface.texture_size<32 || (options.surface.texture_size&(options.surface.texture_size-1)) || options.surface.target_faces<4 || !options.decoder.chunk_rows || !options.decoder.max_voxels || !options.mesh.max_triangles)
            throw std::invalid_argument("worker configuration outside supported bounds");
        fs::path input=fs::canonical(flags.at("--input")),output=fs::absolute(flags.at("--output"));
        auto load=[&](const std::string& name,size_t bound){return pixal::read_input_array(input/(name+".npy"),bound);};
        auto low=load("rgb_low",3*1024*1024),high=load("rgb_high",3*1024*1024),camera=load("camera",3),samplers=load("samplers",21);
        if (low.shape.size()!=3 || high.shape.size()!=3 || low.shape[0]!=3 || high.shape[0]!=3 || low.shape[1]!=low.shape[2] || high.shape[1]!=high.shape[2] || camera.shape!=std::vector<size_t>{3} || samplers.shape!=std::vector<size_t>{3,7})
            throw std::invalid_argument("worker input shape differs");
        auto norm=[&](const std::string& name){auto value=load(name,8192);if (value.shape.size()!=2 || value.shape[0]!=2) throw std::invalid_argument("invalid worker normalization");size_t channels=value.shape[1];return pixal::LatentNormalization{{value.data.begin(),value.data.begin()+channels},{value.data.begin()+channels,value.data.end()}};};
        auto shape=norm("shape_norm"),texture=norm("texture_norm");size_t offset=0;
        for (auto* sampler:{&options.ss_sampler,&options.shape_sampler,&options.texture_sampler}) {
            float steps=samplers.data[offset];if (steps<1 || steps>1000 || steps!=std::floor(steps)) throw std::invalid_argument("invalid worker sampler steps");
            sampler->steps=int(steps);sampler->rescale_t=samplers.data[offset+1];sampler->guidance_strength=samplers.data[offset+2];sampler->guidance_rescale=samplers.data[offset+3];
            sampler->interval_start=samplers.data[offset+4];sampler->interval_end=samplers.data[offset+5];sampler->sigma_min=samplers.data[offset+6];pixal::validate_flow_sampler(*sampler);offset+=7;
        }
        if (!fs::create_directory(output)) throw std::invalid_argument("worker output exists");
        owned=output;if (chmod(output.c_str(),0700)!=0) throw std::runtime_error("cannot protect worker output");
        options.cancelled=[](){return interrupted!=0;};
        options.progress=[](const std::string& stage,int done,int total){std::cout<<"stage="<<stage<<" "<<done<<"/"<<total<<std::endl;};
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(gpu?ggml_backend_vk_init(device):ggml_backend_cpu_init(),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested worker backend unavailable");
        if (!gpu) ggml_backend_cpu_set_n_threads(backend.get(),2);
        trellis::g_no_fa=true;
        pixal::PipelineFrames frames{low.data,high.data,int(low.shape[1]),int(high.shape[1])};
        pixal::Camera cam{camera.data[0],camera.data[1],camera.data[2],frames.low_size};
        pixal::SurfaceProvenance provenance{source_kind,flags.at("--source-sha"),flags.at("--input-sha"),options.seed};
        auto result=pixal::generate_glb(models,backend.get(),frames,cam,shape,texture,(output/"asset.glb").string(),provenance,options);
        if (interrupted) throw std::runtime_error("Pixal worker cancelled before report publication");
        std::ofstream report(output/"report.json");report.exceptions(std::ios::badbit|std::ios::failbit);
        report<<"{\"source_kind\":\""<<result.source_kind<<"\",\"backend\":\""<<kind<<"\",\"device_index\":"<<device<<",\"precision\":\"float32\",\"seed\":"<<options.seed
            <<",\"source_sha256\":\""<<provenance.source_sha256<<"\",\"input_sha256\":\""<<provenance.input_sha256<<"\",\"rng_algorithm\":\""<<result.rng_algorithm
            <<"\",\"ss_tokens\":"<<result.ss_tokens<<",\"upsampled_tokens\":"<<result.upsampled_tokens<<",\"hr_tokens\":"<<result.hr_tokens
            <<",\"actual_resolution\":"<<result.actual_resolution<<",\"token_budget_met\":"<<(result.token_budget_met?"true":"false")
            <<",\"glb_bytes\":"<<result.surface.glb_bytes<<",\"atlas_faces\":"<<result.surface.simplified_faces<<",\"texture_size\":"<<options.surface.texture_size<<"}\n";
        report.close();owned.clear();return 0;
    } catch (const std::exception& error) {
        if (!owned.empty()) {std::error_code ignored;fs::remove_all(owned,ignored);}
        std::cerr<<error.what()<<'\n';return 1;
    }
}
