// Private local evaluation driver. Host admission/renewal belongs to its caller.
#include "pipeline.h"
#include "ggml-cpu.h"
#include "ggml-vulkan.h"
#include "npy.h"
#include <cmath>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sys/stat.h>
namespace pixal=mediaforge::pixal;
namespace fs=std::filesystem;
namespace trellis { extern bool g_no_fa; }
int main(int argc,char** argv) {
    fs::path owned;
    try {
        if (argc<4) throw std::invalid_argument("usage: pixal-pipeline-check input output cpu|vulkan --dino path --naf path --ss-flow path --ss-decoder path --shape-lr path --shape-hr path --shape-decoder path --texture-flow path --texture-decoder path --source-sha hash --input-sha hash [--device N] [--diagnostics] [--native-noise] [--fault name]");
        fs::path input=fs::canonical(argv[1]),output=fs::absolute(argv[2]);std::string kind=argv[3];
        std::map<std::string,std::string> flags;bool diagnostics=false,native_noise=false;
        const std::vector<std::string> valid={"--dino","--naf","--ss-flow","--ss-decoder","--shape-lr","--shape-hr","--shape-decoder","--texture-flow","--texture-decoder","--source-sha","--input-sha","--device","--fault"};
        for (int i=4;i<argc;++i) {
            std::string flag=argv[i];
            if (flag=="--diagnostics") diagnostics=true;
            else if (flag=="--native-noise") native_noise=true;
            else if (i+1<argc && std::find(valid.begin(),valid.end(),flag)!=valid.end() && !flags.count(flag)) flags[flag]=argv[++i];
            else throw std::invalid_argument("invalid pipeline driver argument");
        }
        bool gpu=kind=="vulkan";
        if ((kind!="cpu" && !gpu) || gpu!=(flags.count("--device")!=0)) throw std::invalid_argument("explicit pipeline backend/device required");
        pixal::PipelineModels models{flags.at("--dino"),flags.at("--naf"),flags.at("--ss-flow"),flags.at("--ss-decoder"),flags.at("--shape-lr"),flags.at("--shape-hr"),flags.at("--shape-decoder"),flags.at("--texture-flow"),flags.at("--texture-decoder")};
        if (!fs::create_directory(output)) throw std::invalid_argument("pipeline output exists");
        owned=output;if (chmod(output.c_str(),0700)!=0) throw std::runtime_error("cannot protect pipeline output directory");
        auto source_kind=pixal::inspect_pipeline(models);
        auto load=[&](const std::string& name) { auto v=npy::load((input/(name+".npy")).string());if (v.numel()>4000000) throw std::invalid_argument("pipeline fixture exceeds bound");return v; };
        auto integer=[](float x) { if (!std::isfinite(x) || x!=std::floor(x) || x<0 || x>1000000) throw std::invalid_argument("invalid pipeline fixture integer");return int(x); };
        auto low=load("rgb_low"),high=load("rgb_high"),camera=load("camera"),settings=load("settings"),samplers=load("samplers");
        if (low.shape.size()!=3 || high.shape.size()!=3 || low.shape[0]!=3 || high.shape[0]!=3 || low.shape[1]!=low.shape[2] || high.shape[1]!=high.shape[2] || low.shape[1]>1024 || high.shape[1]>1024 || camera.data.size()!=3 || settings.data.size()!=8 || samplers.data.size()!=21)
            throw std::invalid_argument("invalid pipeline fixture layout");
        auto norm=[&](const std::string& name) {auto a=load(name);if (a.shape.size()!=2 || a.shape[0]!=2) throw std::invalid_argument("invalid pipeline norm fixture");size_t half=a.data.size()/2;return pixal::LatentNormalization{{a.data.begin(),a.data.begin()+half},{a.data.begin()+half,a.data.end()}};};
        auto sn=norm("shape_norm"),tn=norm("texture_norm");
        pixal::PipelineFrames frames{low.data,high.data,int(low.shape[1]),int(high.shape[1])};
        pixal::Camera cam{camera.data[0],camera.data[1],camera.data[2],frames.low_size};
        pixal::PipelineOptions options;options.f32_arithmetic=true;options.resolution=integer(settings.data[0]);options.max_tokens=integer(settings.data[1]);
        options.naf_lr=integer(settings.data[2]);options.naf_hr=integer(settings.data[3]);options.naf_texture=integer(settings.data[4]);
        options.surface.texture_size=integer(settings.data[5]);options.surface.target_faces=integer(settings.data[6]);options.seed=integer(settings.data[7]);
        options.decoder.chunk_rows=64;options.decoder.max_voxels=100000;options.mesh.max_voxels=100000;options.mesh.max_triangles=200000;
        int offset=0;
        for (auto* p:{&options.ss_sampler,&options.shape_sampler,&options.texture_sampler}) {
            p->steps=integer(samplers.data[offset]);p->rescale_t=samplers.data[offset+1];p->guidance_strength=samplers.data[offset+2];p->guidance_rescale=samplers.data[offset+3];p->interval_start=samplers.data[offset+4];p->interval_end=samplers.data[offset+5];p->sigma_min=samplers.data[offset+6];offset+=7;
        }
        std::string fault=flags["--fault"],events;bool stop=false;
        options.progress=[&](const std::string& phase,int done,int total) {
            std::cout << "stage=" << phase << " " << done << "/" << total << std::endl;
            if (!events.empty()) events+=",";
            events+="[\""+phase+"\","+std::to_string(done)+","+std::to_string(total)+"]";
            if (fault=="cancel_"+phase) stop=true;
        };
        options.cancelled=[&]() {return stop || fault=="cancel_before";};
        if (diagnostics) options.diagnostic=[&](const std::string& name,const std::vector<float>& v) {npy::save((output/("actual_"+name+".npy")).string(),v.data(),{int64_t(v.size())});};
        pixal::PipelineNoise noise;
        if (!native_noise) noise=[&](const std::string& stage,size_t rows,int channels) {
            auto a=load(stage+"_noise");if (a.shape!=std::vector<int64_t>{int64_t(rows),channels}) throw std::invalid_argument("pipeline fixture noise shape mismatch");
            if (fault=="noise_extent") a.data.pop_back();
            if (fault=="noise_nan") a.data[0]=std::numeric_limits<float>::quiet_NaN();
            return a.data;
        };
        pixal::SurfaceProvenance provenance{source_kind,flags.at("--source-sha"),flags.at("--input-sha"),options.seed};
        if (fault=="nan_rgb") frames.low[0]=std::numeric_limits<float>::infinity();
        if (fault=="camera") cam.distance=0;
        if (fault=="resolution") options.resolution=512;
        if (fault=="budget") options.max_tokens=0;
        if (fault=="norm") sn.std[0]=0;
        if (fault=="provenance") provenance.source_kind="checkpoint";
        if (fault=="no_remesh") options.surface.remesh=false;
        if (fault=="empty_allowed") options.mesh.require_faces=false;
        if (fault=="target") options.naf_hr=0;
        if (fault=="sampler") options.texture_sampler.steps=0;
        if (fault=="output_exists") {std::ofstream sentinel(output/"asset.glb");sentinel << "preserve";}
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(gpu?ggml_backend_vk_init(std::stoi(flags.at("--device"))):ggml_backend_cpu_init(),ggml_backend_free);
        if (!backend) throw std::runtime_error("requested pipeline backend unavailable");
        if (!gpu) ggml_backend_cpu_set_n_threads(backend.get(),2);
        trellis::g_no_fa=true;
        auto result=pixal::generate_glb(models,backend.get(),frames,cam,sn,tn,(output/"asset.glb").string(),provenance,options,noise);
        std::ofstream report(output/"report.json");report.exceptions(std::ios::badbit|std::ios::failbit);
        report << "{\"source_kind\":\"" << result.source_kind << "\",\"rng_algorithm\":\"" << result.rng_algorithm << "\",\"ss_tokens\":" << result.ss_tokens << ",\"upsampled_tokens\":" << result.upsampled_tokens
            << ",\"hr_tokens\":" << result.hr_tokens << ",\"actual_resolution\":" << result.actual_resolution << ",\"token_budget_met\":" << (result.token_budget_met?"true":"false") << ",\"glb_bytes\":" << result.surface.glb_bytes
            << ",\"original_faces\":" << result.surface.original_faces << ",\"atlas_faces\":" << result.surface.simplified_faces << ",\"texture_size\":" << options.surface.texture_size << ",\"events\":[" << events << "]}\n";
        report.close();owned.clear();return 0;
    } catch (const std::exception& e) {
        if (!owned.empty()) {std::error_code ignored;fs::remove_all(owned,ignored);}
        std::cerr << e.what() << '\n';return 1;
    }
}
