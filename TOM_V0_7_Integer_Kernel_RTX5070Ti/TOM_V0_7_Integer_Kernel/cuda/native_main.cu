#include <cuda_runtime.h>
#include "tom/native_image.hpp"
#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace tom::native_gpu {
using Word=std::uint32_t;
using Wide=std::uint64_t;

void check(cudaError_t error,const char* operation){
    if(error!=cudaSuccess)throw std::runtime_error(std::string(operation)+": "+cudaGetErrorString(error));
}
template<class T>class Buffer {
    T* pointer_=nullptr;
    std::size_t count_=0;
public:
    explicit Buffer(std::size_t count):count_(count){
        if(count>std::numeric_limits<std::size_t>::max()/sizeof(T))throw std::overflow_error("native device allocation extent");
        if(count)check(cudaMalloc(reinterpret_cast<void**>(&pointer_),count*sizeof(T)),"allocate native device data");
    }
    ~Buffer(){if(pointer_)cudaFree(pointer_);}
    Buffer(const Buffer&)=delete;Buffer& operator=(const Buffer&)=delete;
    T* data()const{return pointer_;}
    std::size_t size()const{return count_;}
    void upload(const T* input,std::size_t count){
        if(count>count_)throw std::out_of_range("native upload extent");
        if(count)check(cudaMemcpy(pointer_,input,count*sizeof(T),cudaMemcpyHostToDevice),"upload native terms and histories");
    }
    void download(T* output,std::size_t count,std::size_t offset)const{
        if(offset>count_||count>count_-offset)throw std::out_of_range("native download extent");
        if(count)check(cudaMemcpy(output,pointer_+offset,count*sizeof(T),cudaMemcpyDeviceToHost),"download native terms and histories");
    }
};
struct Options {
    std::string input,output,json,expected_templates,resume;
    Word repeat=1,warmup=0,block=128,shard_cases=0,percent=0,generated_cases=0;
    bool help=false,verify=false,generate_given=false;
};
Word number(const std::string& value){
    Wide result=0;const auto parsed=std::from_chars(value.data(),value.data()+value.size(),result);
    if(parsed.ec!=std::errc()||parsed.ptr!=value.data()+value.size()||result>0xffffffffu)
        throw std::invalid_argument("uint32 required: "+value);
    return Word(result);
}
Options options(int argc,char** argv){
    Options result;
    for(int i=1;i<argc;++i){
        const std::string key=argv[i];
        if(key=="--help"||key=="-h"){result.help=true;continue;}
        if(key=="--verify"){result.verify=true;continue;}
        if(i+1==argc)throw std::invalid_argument("missing value for "+key);
        const std::string value=argv[++i];
        if(key=="--input")result.input=value;
        else if(key=="--output")result.output=value;
        else if(key=="--json")result.json=value;
        else if(key=="--expected-templates")result.expected_templates=value;
        else if(key=="--resume")result.resume=value;
        else if(key=="--repeat")result.repeat=number(value);
        else if(key=="--warmup")result.warmup=number(value);
        else if(key=="--block")result.block=number(value);
        else if(key=="--shard-cases")result.shard_cases=number(value);
        else if(key=="--vram-percent")result.percent=number(value);
        else if(key=="--generate-cases"){result.generated_cases=number(value);result.generate_given=true;}
        else throw std::invalid_argument("unknown option: "+key);
    }
    if(!result.repeat)throw std::invalid_argument("repeat must be positive");
    if(!result.block||result.block>1024||(result.block%32))throw std::invalid_argument("block must be a multiple of 32 in 32..1024");
    if(result.percent>100)throw std::invalid_argument("vram-percent must be 0..100");
    if(result.percent&&result.generated_cases)throw std::invalid_argument("generate-cases and vram-percent are mutually exclusive");
    if(result.generate_given&&!result.generated_cases)throw std::invalid_argument("generate-cases must be positive");
    return result;
}
std::string escape(const std::string& value){
    std::string result;
    for(unsigned char c:value){if(c=='"'||c=='\\')result+='\\';if(c>=32)result+=char(c);}
    return result;
}
void put_word(std::ostream& output,Word value){
    const char bytes[4]{char(value&255),char((value>>8)&255),char((value>>16)&255),char(value>>24)};
    output.write(bytes,4);
}
__global__ void execute(const Word* input,Word* output,tom::native::Config config,Word cases){
    for(Wide index=Wide(blockIdx.x)*blockDim.x+threadIdx.x;index<cases;index+=Wide(blockDim.x)*gridDim.x)
        tom::native::evaluate(input+index*config.case_words,output+index*config.result_words,config);
}
__global__ void generate(const Word* templates,Word template_cases,Word* input,tom::native::Config config,Word first,Word cases){
    for(Wide index=Wide(blockIdx.x)*blockDim.x+threadIdx.x;index<cases;index+=Wide(blockDim.x)*gridDim.x){
        const Wide identity=Wide(first)+index;
        const Word* source=templates+(identity%template_cases)*config.case_words;
        Word* target=input+index*config.case_words;
        for(Word word=0;word<config.case_words;++word)target[word]=source[word];
        const Word old=tom::native::old_history_offset(config),proposed=tom::native::new_history_offset(config);
        target[old]=target[proposed]=Word(identity);
        target[old+1]=target[proposed+1]=Word(identity>>32);
    }
}
// All-case totals are separate from timed structural evaluation and from export.
__global__ void aggregate(const Word* output,tom::native::Config config,Word cases,unsigned long long* totals){
    unsigned long long sum[16]{};
    for(Wide index=Wide(blockIdx.x)*blockDim.x+threadIdx.x;index<cases;index+=Wide(blockDim.x)*gridDim.x){
        const Word* result=output+index*config.result_words;
        sum[result[0]?1:0]++;
        for(unsigned bit=0;bit<8;++bit)if(result[0]&(1u<<bit))++sum[2+bit];
        sum[10]+=result[7];sum[11]+=result[8];sum[12]+=result[9];sum[13]+=result[10];
        sum[14]+=result[4];sum[15]+=result[5];
    }
    __shared__ unsigned long long partial[16][8];
    for(unsigned field=0;field<16;++field){
        for(unsigned delta=16;delta;delta>>=1)sum[field]+=__shfl_down_sync(0xffffffffu,sum[field],delta);
        if((threadIdx.x&31)==0)partial[field][threadIdx.x>>5]=sum[field];
    }
    __syncthreads();
    if(threadIdx.x<32)for(unsigned field=0;field<16;++field){
        unsigned long long value=threadIdx.x<(blockDim.x>>5)?partial[field][threadIdx.x]:0;
        for(unsigned delta=16;delta;delta>>=1)value+=__shfl_down_sync(0xffffffffu,value,delta);
        if(threadIdx.x==0)atomicAdd(totals+field,value);
    }
}
__global__ void verify_expected(const Word* output,const Word* expected,Word template_cases,
    tom::native::Config config,Word first,Word cases,unsigned long long* totals){
    unsigned long long mismatches=0,checked=0;
    const Word old=tom::native::original_offset()+tom::native::old_history_offset(config);
    const Word proposed=tom::native::original_offset()+tom::native::new_history_offset(config);
    const Word committed=tom::native::committed_history_offset(config);
    for(Wide index=Wide(blockIdx.x)*blockDim.x+threadIdx.x;index<Wide(cases)*config.result_words;index+=Wide(blockDim.x)*gridDim.x){
        const Wide identity=Wide(first)+index/config.result_words;
        const Word word=Word(index%config.result_words);
        Word wanted=expected[(identity%template_cases)*config.result_words+word];
        if(word==old||word==proposed||word==committed)wanted=Word(identity);
        else if(word==old+1||word==proposed+1||word==committed+1)wanted=Word(identity>>32);
        if(output[index]!=wanted)++mismatches;
        ++checked;
    }
    for(unsigned delta=16;delta;delta>>=1){
        mismatches+=__shfl_down_sync(0xffffffffu,mismatches,delta);
        checked+=__shfl_down_sync(0xffffffffu,checked,delta);
    }
    __shared__ unsigned long long partial[2][8];
    if((threadIdx.x&31)==0){partial[0][threadIdx.x>>5]=mismatches;partial[1][threadIdx.x>>5]=checked;}
    __syncthreads();
    if(threadIdx.x<32){
        mismatches=threadIdx.x<(blockDim.x>>5)?partial[0][threadIdx.x]:0;
        checked=threadIdx.x<(blockDim.x>>5)?partial[1][threadIdx.x]:0;
        for(unsigned delta=16;delta;delta>>=1){
            mismatches+=__shfl_down_sync(0xffffffffu,mismatches,delta);
            checked+=__shfl_down_sync(0xffffffffu,checked,delta);
        }
        if(threadIdx.x==0){atomicAdd(totals,mismatches);atomicAdd(totals+1,checked);}
    }
}
struct Shard {
    Word first_case,cases;
    Buffer<Word> input,output;
    Shard(Word first,Word count,const tom::native::Config& config):first_case(first),cases(count),
        input(std::size_t(count)*config.case_words),output(std::size_t(count)*config.result_words){}
};
unsigned grid(Word cases,Word block,int sm_count){
    return unsigned(std::max(Wide(1),std::min((Wide(cases)+block-1)/block,Wide(std::max(1,sm_count))*16)));
}
} // namespace tom::native_gpu

int main(int argc,char** argv){
    using namespace tom::native_gpu;
    try{
        const Options o=options(argc,argv);
        if(o.help){
            std::cout<<"Bounded TOM V0.7 native structural executor on CUDA\n"
                <<"--input FILE [--output FILE --repeat N --warmup N --block N --shard-cases N --verify --json FILE]\n"
                <<"--generate-cases N | --vram-percent N: input supplies 1..8 native templates; unique IDs replace the first 8 retained history bytes.\n"
                <<"--expected-templates FILE: independently supplied TOR1 template results checked against every generated output word.\n"
                <<"--resume PRIOR_RESULTS_FILE: bind supplied old history and previous order to a prior file-mode result.\n"
                <<"Repeat evaluates the same supplied proposals independently; it does not manufacture later history.\n";
            return 0;
        }
        if(o.input.empty())throw std::invalid_argument("input file is required");
        tom::native::protect_paths(o.output,o.json,{o.input,o.resume,o.expected_templates});
        const auto batch=tom::native::load_batch(o.input);
        const auto& config=batch.config;
        if(!batch.cases)throw std::invalid_argument("native input requires at least one case");
        const bool generated=o.generated_cases||o.percent;
        if(!o.expected_templates.empty()&&!generated)throw std::invalid_argument("expected-templates requires generated native mode");
        if(!o.resume.empty()){
            if(generated)throw std::invalid_argument("resume cannot be combined with generated native mode");
            tom::native::validate_resume(batch,o.resume);
        }
        if(generated){
            if(batch.cases>8)throw std::invalid_argument("generated native mode requires 1..8 templates");
            std::vector<Word> result(config.result_words);
            for(Word i=0;i<batch.cases;++i){
                const Word* source=batch.values.data()+std::size_t(i)*config.case_words;
                if(source[2]<8||source[3]<source[2]||source[3]>Wide(config.history_capacity_words)*4)
                    throw std::invalid_argument("generated native templates need a preserved history prefix of at least 8 bytes");
                for(Word byte=0;byte<source[2];++byte)
                    if(tom::native::byte_at(source+tom::native::old_history_offset(config),byte)!=
                       tom::native::byte_at(source+tom::native::new_history_offset(config),byte))
                        throw std::invalid_argument("generated native template rewrites its completed history prefix");
                tom::native::evaluate(source,result.data(),config);
                if(!result[7]||(result[0]&(tom::native::INVALID|tom::native::CAPACITY)))
                    throw std::invalid_argument("generated native templates must contain valid complete source TOM terms");
            }
        }
        std::vector<Word> expected_values;
        if(!o.expected_templates.empty()){
            std::ifstream reference(o.expected_templates,std::ios::binary|std::ios::ate);
            if(!reference)throw std::runtime_error("cannot open independent native template results");
            const auto length=reference.tellg();reference.seekg(0);
            std::array<Word,16> header{};reference.read(reinterpret_cast<char*>(header.data()),64);
            if(!reference||header!=tom::native::file_header(config,batch.cases,tom::native::OUTPUT_MAGIC))
                throw std::runtime_error("independent native template result header/configuration mismatch");
            const Wide words=Wide(batch.cases)*config.result_words;
            if(length<0||Wide(length)!=64+words*4||words>std::numeric_limits<std::size_t>::max()/4)
                throw std::runtime_error("independent native template result length mismatch");
            expected_values.resize(std::size_t(words));
            reference.read(reinterpret_cast<char*>(expected_values.data()),std::streamsize(words*4));
            if(!reference)throw std::runtime_error("truncated independent native template results");
            for(Word index=0;index<batch.cases;++index){
                const Word* expected=expected_values.data()+std::size_t(index)*config.result_words;
                const Word* original=batch.values.data()+std::size_t(index)*config.case_words;
                if(expected[3]<8||expected[3]>Wide(config.history_capacity_words)*4)
                    throw std::runtime_error("independent native templates must retain complete identity bytes");
                if(!std::equal(original,original+config.case_words,expected+tom::native::original_offset()))
                    throw std::runtime_error("independent native template result does not retain the supplied input template");
            }
        }
        check(cudaSetDevice(0),"select native CUDA device");
        check(cudaFree(nullptr),"initialize native CUDA context");
        cudaDeviceProp properties{};check(cudaGetDeviceProperties(&properties,0),"native CUDA device properties");
        cudaFuncAttributes attributes{};check(cudaFuncGetAttributes(&attributes,execute),"native kernel resource query");
        if(o.block>Word(attributes.maxThreadsPerBlock))throw std::invalid_argument("block exceeds native kernel thread limit");
        int active_blocks=0;
        check(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&active_blocks,execute,int(o.block),0),"native occupancy query");
        Buffer<Word> template_data(generated?batch.values.size():0);
        if(generated)template_data.upload(batch.values.data(),batch.values.size());
        Buffer<unsigned long long> device_totals(16);
        std::array<unsigned long long,16> totals{};device_totals.upload(totals.data(),totals.size());
        Buffer<Word> expected_data(expected_values.size());
        if(!expected_values.empty())expected_data.upload(expected_values.data(),expected_values.size());
        Buffer<unsigned long long> device_verification(expected_values.empty()?0:2);
        std::array<unsigned long long,2> full_verification{};
        if(!expected_values.empty())device_verification.upload(full_verification.data(),full_verification.size());
        std::size_t free_before=0,total_bytes=0;check(cudaMemGetInfo(&free_before,&total_bytes),"native available memory");
        const Wide words_per_case=Wide(config.case_words)+config.result_words;
        Word cases=generated?o.generated_cases:batch.cases;
        if(o.percent){
            const Wide capacity=(Wide(free_before)/100)*o.percent/(4*words_per_case);
            if(!capacity||capacity>0xffffffffu)throw std::runtime_error("selected native memory budget does not fit the case-count ABI");
            cases=Word(capacity);
        }
        if(!words_per_case||Wide(cases)>std::numeric_limits<Wide>::max()/4/words_per_case)
            throw std::overflow_error("complete native allocation extent");
        const Wide working_bytes=Wide(cases)*words_per_case*4;
        if(working_bytes>free_before)throw std::runtime_error("complete native input and output exceed available CUDA memory");
        const Word cap=o.shard_cases?std::min(o.shard_cases,cases):cases;
        std::vector<std::unique_ptr<Shard>> shards;
        for(Word first=0;first<cases;){
            const Word count=std::min(cap,cases-first);
            auto shard=std::make_unique<Shard>(first,count,config);
            if(generated){
                generate<<<grid(count,o.block,properties.multiProcessorCount),o.block>>>(template_data.data(),batch.cases,shard->input.data(),config,first,count);
                check(cudaGetLastError(),"generate distinct retained native histories");
            }else shard->input.upload(batch.values.data()+std::size_t(first)*config.case_words,shard->input.size());
            shards.push_back(std::move(shard));first+=count;
        }
        check(cudaDeviceSynchronize(),"native upload complete");
        auto launch_all=[&](){
            for(const auto& shard:shards){
                execute<<<grid(shard->cases,o.block,properties.multiProcessorCount),o.block>>>(shard->input.data(),shard->output.data(),config,shard->cases);
                check(cudaGetLastError(),"native structural evaluation launch");
            }
        };
        for(Word warmup=0;warmup<o.warmup;++warmup)launch_all();
        check(cudaDeviceSynchronize(),"native warmup complete");
        std::size_t free_after=0,ignored=0;check(cudaMemGetInfo(&free_after,&ignored),"native resident memory");
        const auto begin=std::chrono::steady_clock::now();
        for(Word iteration=0;iteration<o.repeat;++iteration)launch_all();
        check(cudaDeviceSynchronize(),"native structural evaluation complete");
        const auto elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-begin).count();

        const auto count_begin=std::chrono::steady_clock::now();
        for(const auto& shard:shards){
            aggregate<<<grid(shard->cases,256,properties.multiProcessorCount),256>>>(shard->output.data(),config,shard->cases,device_totals.data());
            check(cudaGetLastError(),"aggregate every native result");
        }
        check(cudaDeviceSynchronize(),"native all-case aggregation complete");
        const auto count_elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-count_begin).count();
        device_totals.download(totals.data(),totals.size(),0);
        if(totals[0]+totals[1]!=cases)throw std::runtime_error("native result aggregation missed cases");
        std::chrono::nanoseconds::rep full_verification_ns=0;
        if(!expected_values.empty()){
            const auto verification_begin=std::chrono::steady_clock::now();
            for(const auto& shard:shards){
                verify_expected<<<grid(shard->cases,256,properties.multiProcessorCount),256>>>(shard->output.data(),expected_data.data(),batch.cases,
                    config,shard->first_case,shard->cases,device_verification.data());
                check(cudaGetLastError(),"independent all-word native result verification");
            }
            check(cudaDeviceSynchronize(),"independent all-word native result verification complete");
            full_verification_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-verification_begin).count();
            device_verification.download(full_verification.data(),full_verification.size(),0);
        }
        const bool full_verification_passed=!expected_values.empty()&&!full_verification[0]&&full_verification[1]==Wide(cases)*config.result_words;
        Wide verified_cases=0;
        if(o.verify){
            std::vector<Word> supplied(config.case_words),expected_input(config.case_words),expected(config.result_words),actual(config.result_words);
            for(const auto& shard:shards){
                std::vector<Word> indices;
                const Word head=std::min(Word(4),shard->cases);
                for(Word i=0;i<head;++i)indices.push_back(i);
                for(Word i=std::max(head,shard->cases-std::min(Word(4),shard->cases));i<shard->cases;++i)indices.push_back(i);
                for(Word index:indices){
                    const Wide identity=Wide(shard->first_case)+index;
                    shard->input.download(supplied.data(),supplied.size(),std::size_t(index)*config.case_words);
                    const Word* original=batch.values.data()+std::size_t(generated?identity%batch.cases:identity)*config.case_words;
                    std::copy_n(original,config.case_words,expected_input.data());
                    if(generated){
                        const Word old=tom::native::old_history_offset(config),proposed=tom::native::new_history_offset(config);
                        expected_input[old]=expected_input[proposed]=Word(identity);
                        expected_input[old+1]=expected_input[proposed+1]=Word(identity>>32);
                    }
                    if(supplied!=expected_input)throw std::runtime_error("native generated/uploaded input differs at case "+std::to_string(identity));
                    tom::native::evaluate(supplied.data(),expected.data(),config);
                    shard->output.download(actual.data(),actual.size(),std::size_t(index)*config.result_words);
                    if(actual!=expected)throw std::runtime_error("native GPU result differs from shared CPU core at case "+std::to_string(identity));
                    ++verified_cases;
                }
            }
        }
        // Export is optional. Every case remains resident; no allocation is
        // recycled between launches. Requested output contains complete results.
        Wide result_digest=1469598103934665603ull;
        if(!o.output.empty()){
            tom::native::AtomicOutput destination(o.output);auto& output=destination.stream();
            const auto header=tom::native::file_header(config,cases,tom::native::OUTPUT_MAGIC);
            for(Word value:header)put_word(output,value);
            std::vector<Word> chunk(std::size_t(std::min(Wide(1)<<18,Wide(cases)*config.result_words)));
            for(const auto& shard:shards)for(std::size_t offset=0;offset<shard->output.size();){
                const auto count=std::min(chunk.size(),shard->output.size()-offset);
                shard->output.download(chunk.data(),count,offset);
                for(std::size_t i=0;i<count;++i){const Word value=chunk[i];put_word(output,value);result_digest^=value;result_digest*=1099511628211ull;}
                if(!output)throw std::runtime_error("complete native result write failed");
                offset+=count;
            }
            destination.publish();
        }
        std::ostringstream report;
        report<<"{\"name\":\"TOM V0.7 bounded native structural executor\",\"gpu_executed\":true,\"device\":\""<<escape(properties.name)
            <<"\",\"input\":\""<<escape(o.input)<<"\",\"output\":\""<<escape(o.output)<<"\",\"cases\":"<<cases
            <<",\"resume\":\""<<escape(o.resume)<<"\",\"resume_validated\":"<<(!o.resume.empty()?"true":"false")
            <<",\"generated\":"<<(generated?"true":"false")<<",\"template_cases\":"<<(generated?batch.cases:0)<<",\"requested_vram_percent\":"<<o.percent
            <<",\"repeat\":"<<o.repeat<<",\"warmup\":"<<o.warmup<<",\"shards\":"<<shards.size()<<",\"block_threads\":"<<o.block
            <<",\"compute_launches\":"<<Wide(o.repeat)*shards.size()<<",\"warmup_launches\":"<<Wide(o.warmup)*shards.size()
            <<",\"case_words\":"<<config.case_words<<",\"result_words\":"<<config.result_words<<",\"working_bytes\":"<<working_bytes
            <<",\"free_before_bytes\":"<<free_before<<",\"free_after_bytes\":"<<free_after<<",\"total_device_bytes\":"<<total_bytes
            <<",\"elapsed_compute_host_ns\":"<<elapsed<<",\"result_digest\":"<<(o.output.empty()?"null":std::to_string(result_digest))<<",\"accepted_cases\":"<<totals[0]
            <<",\"not_committed_cases\":"<<totals[1]<<",\"status_bit_counts\":[";
        for(std::size_t i=0;i<8;++i){if(i)report<<',';report<<totals[2+i];}
        report<<"],\"sm_count\":"<<properties.multiProcessorCount<<",\"registers_per_thread\":"<<attributes.numRegs
            <<",\"local_bytes_per_thread\":"<<attributes.localSizeBytes<<",\"theoretical_active_blocks_per_sm\":"<<active_blocks
            <<",\"source_tom_cases\":"<<totals[10]<<",\"inverse_occam_rewrites\":"<<totals[11]<<",\"alias_rewrites\":"<<totals[12]
            <<",\"optional_scalar_log_echo_zero_proofs\":"<<totals[13]<<",\"resolved_requests\":"<<totals[14]<<",\"unresolved_requests\":"<<totals[15]
            <<",\"aggregation_elapsed_host_ns\":"<<count_elapsed<<",\"aggregation_in_compute_timing\":false"
            <<",\"full_word_verification\":{\"enabled\":"<<(!expected_values.empty()?"true":"false")
            <<",\"reference\":\""<<escape(o.expected_templates)<<"\",\"passed\":"<<(full_verification_passed?"true":"false")
            <<",\"checked_words\":"<<full_verification[1]<<",\"expected_words\":"<<Wide(cases)*config.result_words<<",\"mismatched_words\":"<<full_verification[0]
            <<",\"elapsed_host_ns\":"<<full_verification_ns<<",\"in_compute_timing\":false"
            <<",\"scope\":\"every word of every generated result compared with independently supplied template bytes; only six retained-history identity words are substituted; verifier does not evaluate native terms\"}"
            <<",\"verified_cases\":"<<verified_cases<<",\"all_cases_verified\":"<<(o.verify&&verified_cases==cases?"true":"false")
            <<",\"verification_scope\":\"first and last up to four cases of every shard; generated inputs checked and complete results compared with shared CPU core\""
            <<",\"exported_cases\":"<<(o.output.empty()?0:cases)<<",\"exported_bytes\":"<<(o.output.empty()?0:64+Wide(cases)*config.result_words*4)
            <<",\"export_in_compute_timing\":false,\"repeat_semantics\":\"independent reevaluation of the same supplied proposals\""
            <<",\"generation_semantics\":\"round-robin native templates; unique global case ID replaces first eight old and proposed history bytes\""
            <<",\"scope\":\"Actual bound native terms, canonical rewrites, guarded requests and complete finite history; unspecified transformations remain explicit open laws.\"}";
        const std::string text=report.str();std::cout<<text<<'\n';
        tom::native::emit(text,o.json);
        if(!expected_values.empty()&&!full_verification_passed){std::cerr<<"native independent all-word verification failed\n";return 1;}
        return 0;
    }catch(const std::exception& error){std::cerr<<"tom_native_cuda: "<<error.what()<<'\n';return 1;}
}
