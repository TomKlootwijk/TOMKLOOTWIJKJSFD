// TOM V0.7 validation backend for SM120. The SDF declaration tape describes
// the evaluator and the programs. CUDA machine instructions remain the explicit
// physical bootstrap. No source-native spatial graph or metric is introduced.
#include <cuda_runtime.h>
#include "tom/cli.hpp"
#include <memory>
namespace tom::gpu {
inline void check(cudaError_t code,const char* operation) {
    if(code!=cudaSuccess)throw std::runtime_error(std::string(operation)+": "+cudaGetErrorString(code));
}
template<class T>class Buffer {
    T* pointer_=nullptr;std::size_t size_=0;
public:
    explicit Buffer(std::size_t n):size_(n) {
        if(n>std::numeric_limits<std::size_t>::max()/sizeof(T))throw std::overflow_error("device allocation size");
        if(n)check(cudaMalloc(reinterpret_cast<void**>(&pointer_),n*sizeof(T)),"cudaMalloc");
    }
    ~Buffer(){if(pointer_)cudaFree(pointer_);}Buffer(const Buffer&)=delete;Buffer& operator=(const Buffer&)=delete;
    T* data()const{return pointer_;}std::size_t size()const{return size_;}
    void upload(const T* source,std::size_t n,std::size_t offset=0) {
        if(offset>size_||n>size_-offset)throw std::out_of_range("device upload extent");
        check(cudaMemcpy(pointer_+offset,source,n*sizeof(T),cudaMemcpyHostToDevice),"upload packed fields");
    }
    void download(T* destination,std::size_t n,std::size_t offset=0)const {
        if(offset>size_||n>size_-offset)throw std::out_of_range("device download extent");
        check(cudaMemcpy(destination,pointer_+offset,n*sizeof(T),cudaMemcpyDeviceToHost),"download packed fields");
    }
};
class Texture {
    cudaTextureObject_t object_=0;
public:
    Texture(const Word* pointer,std::size_t words) {
        cudaResourceDesc r{};r.resType=cudaResourceTypeLinear;
        r.res.linear.devPtr=const_cast<Word*>(pointer);
        r.res.linear.desc=cudaCreateChannelDesc<unsigned int>();
        r.res.linear.sizeInBytes=words*sizeof(Word);
        cudaTextureDesc d{};d.readMode=cudaReadModeElementType;
        d.normalizedCoords=0;d.filterMode=cudaFilterModePoint;d.addressMode[0]=cudaAddressModeClamp;
        check(cudaCreateTextureObject(&object_,&r,&d,nullptr),"create unsigned integer texture");
    }
    ~Texture(){if(object_)cudaDestroyTextureObject(object_);}Texture(const Texture&)=delete;
    cudaTextureObject_t get()const{return object_;}
};
template<int Backend>struct Reader {
    const Word* atlas;const Word* previous;
    cudaTextureObject_t atlas_texture,previous_texture;
    __device__ __forceinline__ Word definition(Word address)const {
        if constexpr(Backend==0)return tex1Dfetch<unsigned int>(atlas_texture,static_cast<int>(address));
        else return atlas[address];
    }
    __device__ __forceinline__ Word data(Word address)const {
        if constexpr(Backend==1)return previous[address];
        else return tex1Dfetch<unsigned int>(previous_texture,static_cast<int>(address));
    }
};
template<int Backend,bool Lowered>
__global__ void execute_kernel(const Word* definition,const Word* old,
    cudaTextureObject_t definition_texture,cudaTextureObject_t old_texture,
    Word* scratch,Word* next,Header h,Word words) {
    extern __shared__ Word shared_definition[];
    const Word* image=definition;
    if constexpr(Backend==2) {
        for(Word i=threadIdx.x;i<h.atlas_words;i+=blockDim.x)shared_definition[i]=definition[i];
        __syncthreads();image=shared_definition;
    }
    Reader<Backend> reader{image,old,definition_texture,old_texture};
    for(Word w=blockIdx.x*blockDim.x+threadIdx.x;w<words;w+=blockDim.x*gridDim.x)
        transition<Lowered>(reader,scratch,next,h,words,w);
}
__global__ void initialize(const Word* definition,Header h,Word* state,Word words,Wide first_word) {
    for(Word w=blockIdx.x*blockDim.x+threadIdx.x;w<words;w+=blockDim.x*gridDim.x) {
        Wide global=first_word+w;
        for(Word id=0;id<h.records;++id) {
            const Word* r=definition+id*16;if(r[0]!=State)continue;
            Word value=0;
            if(r[2]==1)value=FULL;
            else if(r[2]==2)for(Word bit=0;bit<32;++bit)value|=Word((((global<<5)+bit)>>r[3])&1u)<<bit;
            else if(r[2]==3)value=seed_mix(Word(global)^Word(global>>32)^r[3]);
            state[r[1]*words+w]=value;
        }
    }
}
__global__ void count_state(const Word* state,Word slot,Word words,unsigned long long* total) {
    unsigned long long sum=0;
    for(Word w=blockIdx.x*blockDim.x+threadIdx.x;w<words;w+=blockDim.x*gridDim.x)
        sum+=__popc(state[slot*words+w]);
    for(unsigned offset=16;offset;offset>>=1)sum+=__shfl_down_sync(0xffffffffu,sum,offset);
    __shared__ unsigned long long warp_sums[8];
    if((threadIdx.x&31u)==0)warp_sums[threadIdx.x>>5]=sum;
    __syncthreads();
    if(threadIdx.x<32){
        sum=threadIdx.x<(blockDim.x>>5)?warp_sums[threadIdx.x]:0;
        for(unsigned offset=16;offset;offset>>=1)sum+=__shfl_down_sync(0xffffffffu,sum,offset);
        if(threadIdx.x==0)atomicAdd(total,sum);
    }
}
struct KernelResources {
    cudaFuncAttributes attributes{};
    int active_blocks_per_sm=0;
    std::size_t dynamic_shared_bytes=0;
};
template<int Backend,bool Lowered>
KernelResources kernel_resources(Word block,std::size_t atlas_bytes) {
    KernelResources result;result.dynamic_shared_bytes=Backend==2?atlas_bytes:0;
    check(cudaFuncGetAttributes(&result.attributes,execute_kernel<Backend,Lowered>),"query compute kernel attributes");
    check(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&result.active_blocks_per_sm,execute_kernel<Backend,Lowered>,
        int(block),result.dynamic_shared_bytes),"query theoretical compute occupancy");
    return result;
}
template<bool Lowered>
KernelResources kernel_resources(int backend,Word block,std::size_t atlas_bytes) {
    if(backend==0)return kernel_resources<0,Lowered>(block,atlas_bytes);
    if(backend==1)return kernel_resources<1,Lowered>(block,atlas_bytes);
    return kernel_resources<2,Lowered>(block,atlas_bytes);
}
struct Shard {
    Word words;Wide first_word;
    Buffer<Word> state0,state1,scratch;
    std::unique_ptr<Texture> texture0,texture1;
    Shard(const Image& p,Word w,Wide first,bool use_texture):words(w),first_word(first),
      state0(std::size_t(p.h.states)*w),state1(std::size_t(p.h.states)*w),scratch(std::size_t(p.h.scratch_slots)*w) {
        if(use_texture){texture0=std::make_unique<Texture>(state0.data(),state0.size());texture1=std::make_unique<Texture>(state1.data(),state1.size());}
    }
    Buffer<Word>& state(int parity){return parity?state1:state0;}
    cudaTextureObject_t texture(int parity)const {
        const auto& t=parity?texture1:texture0;return t?t->get():0;
    }
};
unsigned blocks(Word words,Word block,const cudaDeviceProp& p,Word blocks_per_sm=8) {
    return unsigned(std::max(Wide(1),std::min((Wide(words)+block-1)/block,
        Wide(std::max(1,p.multiProcessorCount))*blocks_per_sm)));
}
template<bool Lowered>
void launch(Shard& shard,int parity,int backend,const Image& p,const Buffer<Word>& definitions,
            cudaTextureObject_t atlas_texture,Word block,const cudaDeviceProp& properties,Word blocks_per_sm) {
    const Word* old=shard.state(parity).data();Word* next=shard.state(1-parity).data();
    unsigned count=blocks(shard.words,block,properties,blocks_per_sm);
    if(backend==0)execute_kernel<0,Lowered><<<count,block>>>(definitions.data(),old,atlas_texture,shard.texture(parity),shard.scratch.data(),next,p.h,shard.words);
    else if(backend==1)execute_kernel<1,Lowered><<<count,block>>>(definitions.data(),old,0,0,shard.scratch.data(),next,p.h,shard.words);
    else execute_kernel<2,Lowered><<<count,block,std::size_t(p.h.atlas_words)*4>>>(definitions.data(),old,0,shard.texture(parity),shard.scratch.data(),next,p.h,shard.words);
    check(cudaGetLastError(),"TOM field kernel launch");
}
std::string device_info(const cudaDeviceProp& p,unsigned device) {
    std::size_t free=0,total=0;check(cudaMemGetInfo(&free,&total),"query VRAM");
    int runtime=0,driver=0;check(cudaRuntimeGetVersion(&runtime),"runtime version");check(cudaDriverGetVersion(&driver),"driver API version");
    std::ostringstream r;r<<"{\"device\":"<<device<<",\"name\":\""<<escape(p.name)<<"\",\"compute_major\":"<<p.major<<",\"compute_minor\":"<<p.minor
      <<",\"free_bytes\":"<<free<<",\"total_bytes\":"<<total<<",\"shared_default_bytes\":"<<p.sharedMemPerBlock<<",\"shared_optin_bytes\":"<<p.sharedMemPerBlockOptin
      <<",\"linear_texture_max_elements\":"<<p.maxTexture1DLinear<<",\"l2_bytes\":"<<p.l2CacheSize<<",\"sm_count\":"<<p.multiProcessorCount
      <<",\"warp_size\":"<<p.warpSize<<",\"max_threads_per_sm\":"<<p.maxThreadsPerMultiProcessor<<",\"shared_bytes_per_sm\":"<<p.sharedMemPerMultiprocessor
      <<",\"runtime_version\":"<<runtime<<",\"driver_api_version\":"<<driver<<"}";return r.str();
}
} // namespace tom::gpu
int main(int argc,char** argv) {
    using namespace tom;using namespace tom::gpu;
    try {
        Options o=options(argc,argv);if(o.help){usage(true);return 0;}
        check(cudaSetDevice(int(o.device)),"select GPU");check(cudaFree(nullptr),"initialize CUDA context");
        cudaDeviceProp prop{};check(cudaGetDeviceProperties(&prop,int(o.device)),"device properties");
        if(o.info){emit(device_info(prop,o.device),o.json);return 0;}
        if(o.program.empty())throw std::invalid_argument("--program required");
        Image p=load_image(o.program);check_evaluator(p,o);
        for(Word slot:o.count_states)if(slot>=p.h.states)throw std::invalid_argument("count-state slot is outside program state planes");
        if(o.state_mask_slot_given&&o.state_mask_slot>=p.h.states)throw std::invalid_argument("state-mask-slot is outside program state planes");
        int backend=o.backend=="texture"?0:o.backend=="global"?1:2;
        const bool lower=o.evaluator=="lowered",textures=backend!=1;
        const std::size_t atlas_bytes=p.atlas.size()*4;
        if(backend==2) {
            if(atlas_bytes>std::size_t(prop.sharedMemPerBlockOptin))throw std::runtime_error("this image exceeds per-block shared-memory limit; choose texture or global");
            if(lower)check(cudaFuncSetAttribute(execute_kernel<2,true>,cudaFuncAttributeMaxDynamicSharedMemorySize,int(atlas_bytes)),"shared opt-in for lowered evaluator");
            else check(cudaFuncSetAttribute(execute_kernel<2,false>,cudaFuncAttributeMaxDynamicSharedMemorySize,int(atlas_bytes)),"shared opt-in for field evaluator");
        }
        if(textures&&(prop.maxTexture1DLinear<=0||(backend==0&&p.atlas.size()>std::size_t(prop.maxTexture1DLinear))))throw std::runtime_error("definition texture exceeds device limit");
        const auto resources=lower?kernel_resources<true>(backend,o.block,atlas_bytes):kernel_resources<false>(backend,o.block,atlas_bytes);
        Data input;Wide epoch=0,total_words=o.lanes/32;
        if(!o.data.empty()){
            input=load_state(o.data);if(input.slots!=p.h.states)throw std::runtime_error("input data and program slots differ");
            if(o.lanes_given&&o.lanes!=Wide(input.words)*32)throw std::runtime_error("data case count differs from explicit lanes");
            total_words=input.words;epoch=input.epoch;
        }
        if(epoch>std::numeric_limits<Wide>::max()-o.ticks)throw std::runtime_error("epoch would wrap and erase ordering");
        std::vector<unsigned long long> state_totals(o.count_states.size(),0);
        Buffer<unsigned long long> state_counters(state_totals.size());
        if(!state_totals.empty())state_counters.upload(state_totals.data(),state_totals.size());
        const Wide bytes_per_word=(Wide(2)*p.h.states+p.h.scratch_slots)*4;
        std::size_t free_before=0,total_memory=0;check(cudaMemGetInfo(&free_before,&total_memory),"free memory before batch");
        if(o.percent) {
            Wide budget=(Wide(free_before)/100)*o.percent;
            if(budget<=atlas_bytes)throw std::runtime_error("selected budget cannot fit the definition image");
            total_words=(budget-atlas_bytes)/bytes_per_word;
        }
        if(!total_words||total_words>(std::numeric_limits<Wide>::max()-atlas_bytes)/bytes_per_word||total_words*bytes_per_word+atlas_bytes>free_before||total_words>(std::numeric_limits<Wide>::max()/32))throw std::runtime_error("requested batch does not fit queried free memory/address range");
        const Wide state_limit=textures?Wide(prop.maxTexture1DLinear)/p.h.states:Wide(FULL)/p.h.states;
        const Wide automatic_shard_words=std::min({state_limit,Wide(FULL)/p.h.scratch_slots,Wide(1)<<27});
        const Wide shard_words=o.shard_words?std::min(automatic_shard_words,Wide(o.shard_words)):automatic_shard_words;
        if(!shard_words)throw std::runtime_error("one packed lane-word exceeds indexing/texture limit");
        Buffer<Word> definitions(p.atlas.size());definitions.upload(p.atlas.data(),p.atlas.size());
        std::unique_ptr<Texture> atlas_texture;
        if(backend==0)atlas_texture=std::make_unique<Texture>(definitions.data(),definitions.size());
        std::vector<std::unique_ptr<Shard>> shards;
        auto reset_shard=[&](Shard& shard){
            const Word words=shard.words;const Wide first=shard.first_word;
            if(o.data.empty()){
                initialize<<<blocks(words,o.block,prop,o.blocks_per_sm),o.block>>>(definitions.data(),p.h,shard.state0.data(),words,first);
                check(cudaGetLastError(),"seed field generation");
            } else {
                for(Word slot=0;slot<p.h.states;++slot)
                    shard.state0.upload(input.values.data()+std::size_t(slot)*input.words+std::size_t(first),words,std::size_t(slot)*words);
            }
        };
        for(Wide first=0;first<total_words;){
            Word words=Word(std::min(shard_words,total_words-first));auto shard=std::make_unique<Shard>(p,words,first,textures);
            reset_shard(*shard);
            shards.push_back(std::move(shard));first+=words;
        }
        check(cudaDeviceSynchronize(),"initialization complete");
        auto compute_tick=[&](int parity){
            for(auto& s:shards){if(lower)launch<true>(*s,parity,backend,p,definitions,atlas_texture?atlas_texture->get():0,o.block,prop,o.blocks_per_sm);else launch<false>(*s,parity,backend,p,definitions,atlas_texture?atlas_texture->get():0,o.block,prop,o.blocks_per_sm);}
        };
        if(o.warmup){
            int warmup_parity=0;
            for(Word tick=0;tick<o.warmup;++tick){compute_tick(warmup_parity);warmup_parity=1-warmup_parity;}
            check(cudaDeviceSynchronize(),"warmup complete");
            // Restore the exact initial snapshot before recording any observable
            // epoch or trace. Validated schedules overwrite scratch before use.
            for(auto& shard:shards)reset_shard(*shard);
            check(cudaDeviceSynchronize(),"initial state restored after warmup");
        }
        Shard& first=*shards.front();
        auto full_snapshot=[&](int parity){std::vector<Word> values(first.state(parity).size());first.state(parity).download(values.data(),values.size());return values;};
        Trace trace(o.trace,p.h.states,first.words,epoch,Wide(o.ticks)+1);
        if(trace.enabled())trace.append(full_snapshot(0));
        std::size_t free_after=0,ignored=0;check(cudaMemGetInfo(&free_after,&ignored),"memory after allocation");
        int parity=0;auto begin=std::chrono::steady_clock::now();
        for(Word tick=0;tick<o.ticks;++tick){
            compute_tick(parity);
            parity=1-parity;if(trace.enabled())trace.append(full_snapshot(parity));
        }
        check(cudaDeviceSynchronize(),"validation computation complete");auto end=std::chrono::steady_clock::now();
        epoch+=o.ticks;
        const Word sample_words=std::min(first.words,Word(64));Wide sample_digest=0,verified_words=0;
        std::ostringstream shard_reports;shard_reports<<'[';std::size_t summaries_shown=0;
        for(std::size_t index=0;index<shards.size();++index){
            Shard& shard=*shards[index];
            const bool show=shards.size()<=64||index<32||index>=shards.size()-32;
            if(show){
                if(summaries_shown++)shard_reports<<',';
                shard_reports<<"{\"index\":"<<index<<",\"first_word\":"<<shard.first_word<<",\"words\":"<<shard.words
                    <<",\"launch_blocks\":"<<blocks(shard.words,o.block,prop,o.blocks_per_sm)<<",\"samples\":[";
            }
            const Word windows=o.verify&&shard.words>64?2:1;
            for(Word window=0;window<windows;++window){
                if(!o.verify&&index)break;
                const Word offset=window?std::max(Word(64),shard.words-64):0;
                const Word count=std::min(Word(64),shard.words-offset);
                const Wide global_first=shard.first_word+offset;
                std::vector<Word> sample(std::size_t(p.h.states)*count);
                for(Word slot=0;slot<p.h.states;++slot)
                    shard.state(parity).download(sample.data()+std::size_t(slot)*count,count,std::size_t(slot)*shard.words+offset);
                const Wide hash=digest(sample);if(!index&&!window)sample_digest=hash;
                if(o.verify){
                    auto expected=seed(p,count,global_first);
                    if(!o.data.empty())for(Word slot=0;slot<p.h.states;++slot)
                        std::copy_n(input.values.data()+std::size_t(slot)*input.words+std::size_t(global_first),count,expected.data()+std::size_t(slot)*count);
                    std::vector<Word> scratch(std::size_t(p.h.scratch_slots)*count),next(expected.size());
                    for(Word tick=0;tick<o.ticks;++tick){cpu_tick(p,expected,scratch,next,count,false);expected.swap(next);}
                    if(sample!=expected)throw std::runtime_error("GPU result differs from field-defined CPU reference at shard "+std::to_string(index)+", global word "+std::to_string(global_first));
                    verified_words+=count;
                }
                if(show){
                    if(window)shard_reports<<',';
                    shard_reports<<"{\"first_word\":"<<global_first<<",\"words\":"<<count<<",\"digest\":"<<hash
                        <<",\"verified\":"<<(o.verify?"true":"false")<<'}';
                }
            }
            if(show)shard_reports<<"]}";
        }
        shard_reports<<']';
        std::chrono::nanoseconds::rep count_elapsed_ns=0;
        if(!state_totals.empty()){
            const auto count_begin=std::chrono::steady_clock::now();
            for(const auto& shard:shards)for(std::size_t i=0;i<o.count_states.size();++i){
                count_state<<<blocks(shard->words,256,prop,o.blocks_per_sm),256>>>(shard->state(parity).data(),o.count_states[i],shard->words,state_counters.data()+i);
                check(cudaGetLastError(),"all-shard state population count");
            }
            check(cudaDeviceSynchronize(),"all-shard state population counts complete");
            count_elapsed_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-count_begin).count();
            state_counters.download(state_totals.data(),state_totals.size());
        }
        std::ostringstream count_reports;count_reports<<'[';
        for(std::size_t i=0;i<state_totals.size();++i){
            if(i)count_reports<<',';
            if(state_totals[i]>total_words*32)throw std::runtime_error("state population count exceeds lane count");
            count_reports<<"{\"slot\":"<<o.count_states[i]<<",\"ones\":"<<state_totals[i]<<",\"zeros\":"<<total_words*32-state_totals[i]
                <<",\"lanes\":"<<total_words*32<<",\"scope\":\"all_lanes_all_shards\"}";
        }
        count_reports<<']';
        std::ostringstream mask_report;mask_report<<"null";
        if(o.state_mask_slot_given){
            std::ofstream mask(o.state_mask_out,std::ios::binary);
            if(!mask)throw std::runtime_error("cannot save all-shard state mask: "+o.state_mask_out);
            mask.write("TOM7MSK\0",8);write_word(mask,o.state_mask_slot);write_word(mask,1);
            const Wide mask_lanes=total_words*32;
            write_word(mask,Word(mask_lanes));write_word(mask,Word(mask_lanes>>32));
            write_word(mask,Word(epoch));write_word(mask,Word(epoch>>32));
            // At most 1 MiB on the host, even for a mask covering all VRAM.
            std::vector<Word> chunk(std::size_t(std::min(total_words,Wide(1)<<18)));
            for(const auto& shard:shards)for(Word offset=0;offset<shard->words;){
                const Word count=std::min(Word(chunk.size()),shard->words-offset);
                shard->state(parity).download(chunk.data(),count,std::size_t(o.state_mask_slot)*shard->words+offset);
                for(Word i=0;i<count;++i)write_word(mask,chunk[i]);
                if(!mask)throw std::runtime_error("all-shard state mask write failed");
                offset+=count;
            }
            mask.close();if(!mask)throw std::runtime_error("all-shard state mask close failed");
            mask_report.str("");mask_report.clear();
            mask_report<<"{\"path\":\""<<escape(o.state_mask_out)<<"\",\"slot\":"<<o.state_mask_slot<<",\"lanes\":"<<mask_lanes
                <<",\"epoch\":"<<epoch<<",\"version\":1,\"scope\":\"all_lanes_all_shards\",\"data_bytes\":"<<total_words*4<<",\"file_bytes\":"<<32+total_words*4<<'}';
        }
        if(!o.output.empty())save_state(o.output,full_snapshot(parity),p.h.states,first.words,epoch);
        std::ostringstream report;report<<"{\n\"name\":\"TOM\",\"version\":\"0.7-K1\",\"gpu_executed\":true,\"device\":"<<device_info(prop,o.device)<<",\n"
          <<"\"backend\":\""<<o.backend<<"\",\"evaluator\":\""<<o.evaluator<<"\",\"block_threads\":"<<o.block<<",\"lanes\":"<<total_words*32<<",\"ticks\":"<<o.ticks<<",\"epoch\":"<<epoch<<",\"shards\":"<<shards.size()<<",\n"
          <<"\"warmup_ticks\":"<<o.warmup<<",\"compute_executed\":"<<(o.ticks?"true":"false")<<",\"compute_launches\":"<<Wide(o.ticks)*shards.size()<<",\"warmup_compute_launches\":"<<Wide(o.warmup)*shards.size()<<",\n"
          <<"\"shard_words_cap\":"<<o.shard_words<<",\"automatic_shard_words\":"<<automatic_shard_words<<",\"effective_shard_words\":"<<shard_words<<",\"blocks_per_sm\":"<<o.blocks_per_sm<<",\n"
          <<"\"kernel_resources\":{\"registers_per_thread\":"<<resources.attributes.numRegs<<",\"local_bytes_per_thread\":"<<resources.attributes.localSizeBytes
          <<",\"static_shared_bytes\":"<<resources.attributes.sharedSizeBytes<<",\"dynamic_shared_bytes\":"<<resources.dynamic_shared_bytes
          <<",\"max_threads_per_block\":"<<resources.attributes.maxThreadsPerBlock<<",\"theoretical_active_blocks_per_sm\":"<<resources.active_blocks_per_sm
          <<",\"theoretical_active_warps_per_sm\":"<<resources.active_blocks_per_sm*(o.block/prop.warpSize)<<",\"max_warps_per_sm\":"<<prop.maxThreadsPerMultiProcessor/prop.warpSize<<"},\n"
          <<"\"definition_bytes\":"<<atlas_bytes<<",\"working_bytes\":"<<total_words*bytes_per_word<<",\"free_before_bytes\":"<<free_before<<",\"free_after_bytes\":"<<free_after<<",\n"
          <<"\"elapsed_host_ns\":"<<std::chrono::duration_cast<std::chrono::nanoseconds>(end-begin).count()<<",\"sample_digest\":"<<sample_digest<<",\"sample_lanes\":"<<sample_words*32<<",\"sample_verified\":"<<(o.verify?"true":"false")<<",\n"
          <<"\"verification\":{\"enabled\":"<<(o.verify?"true":"false")<<",\"scope\":\"first_and_last_up_to_64_words_per_shard\",\"shards_verified\":"<<(o.verify?shards.size():0)
          <<",\"words_verified\":"<<verified_words<<",\"lanes_verified\":"<<verified_words*32<<",\"all_lane_words_verified\":"<<(o.verify&&verified_words==total_words?"true":"false")<<"},\n"
          <<"\"shard_summaries\":"<<shard_reports.str()<<",\"shard_summaries_shown\":"<<summaries_shown<<",\"shard_summaries_omitted\":"<<shards.size()-summaries_shown<<",\n"
          <<"\"state_counts\":"<<count_reports.str()<<",\"state_count_elapsed_host_ns\":"<<count_elapsed_ns<<",\"state_count_launches\":"<<Wide(o.count_states.size())*shards.size()<<",\"state_counts_in_compute_timing\":false,\n"
          <<"\"state_mask_export\":"<<mask_report.str()<<",\"state_mask_in_compute_timing\":false,\n"
          <<"\"exported_first_shard_lanes\":"<<Wide(first.words)*32<<",\"trace_io_in_timing\":"<<(trace.enabled()?"true":"false")<<",\"setup_in_timing\":false,\"source_physics_validated\":false\n}";
        emit(report.str(),o.json);return 0;
    }catch(const std::exception& e){std::cerr<<"tom_cuda: "<<e.what()<<'\n';return 1;}
}
