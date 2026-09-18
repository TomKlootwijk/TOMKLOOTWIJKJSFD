#pragma once
#include "tom/native_core.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <fstream>
#include <filesystem>
#include <cwctype>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace tom::native {
constexpr Word INPUT_MAGIC=0x314e4f54u,OUTPUT_MAGIC=0x31524f54u;
struct Batch { Config config;Word cases;std::vector<Word> values; };
// Serialize beside the destination, then replace it only after successful close.
// A failed serialization never truncates an existing completed result or report.
class AtomicOutput {
    std::filesystem::path destination_,temporary_;
    std::ofstream stream_;
    bool published_=false;
    static std::filesystem::path reserve(const std::filesystem::path& destination){
        static std::atomic<unsigned long long> sequence{0};
        const auto stamp=std::chrono::steady_clock::now().time_since_epoch().count();
        for(unsigned attempt=0;attempt<128;++attempt){
            auto candidate=destination;
            candidate+=std::filesystem::path(".tmp-"+std::to_string(stamp)+"-"+
                std::to_string(sequence.fetch_add(1,std::memory_order_relaxed)));
#ifdef _WIN32
            HANDLE handle=CreateFileW(candidate.c_str(),GENERIC_WRITE,0,nullptr,
                CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(handle!=INVALID_HANDLE_VALUE){CloseHandle(handle);return candidate;}
            const auto error=GetLastError();
            if(error!=ERROR_FILE_EXISTS&&error!=ERROR_ALREADY_EXISTS)
                throw std::system_error(int(error),std::system_category(),"reserve native output temporary file");
#else
            const int descriptor=::open(candidate.c_str(),O_WRONLY|O_CREAT|O_EXCL,0600);
            if(descriptor>=0){::close(descriptor);return candidate;}
            const int error=errno;
            if(error!=EEXIST)throw std::system_error(error,std::generic_category(),"reserve native output temporary file");
#endif
        }
        throw std::runtime_error("cannot reserve unique native output temporary file");
    }
public:
    explicit AtomicOutput(const std::string& path)
        :destination_(std::filesystem::absolute(path)),temporary_(reserve(destination_)){
        stream_.open(temporary_,std::ios::binary|std::ios::trunc);
        if(!stream_){
            std::error_code ignored;std::filesystem::remove(temporary_,ignored);
            throw std::runtime_error("cannot open native output temporary file");
        }
    }
    AtomicOutput(const AtomicOutput&)=delete;
    AtomicOutput& operator=(const AtomicOutput&)=delete;
    ~AtomicOutput(){
        if(stream_.is_open())stream_.close();
        if(!published_){std::error_code ignored;std::filesystem::remove(temporary_,ignored);}
    }
    std::ofstream& stream(){return stream_;}
    void publish(){
        if(published_)throw std::logic_error("native output already published");
        stream_.flush();
        if(!stream_)throw std::runtime_error("native output flush failed");
        stream_.close();
        if(!stream_)throw std::runtime_error("native output close failed");
#ifdef _WIN32
        if(!MoveFileExW(temporary_.c_str(),destination_.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
            throw std::system_error(int(GetLastError()),std::system_category(),"publish native output");
#else
        std::filesystem::rename(temporary_,destination_);
#endif
        published_=true;
    }
};
inline bool same_path(const std::string& a,const std::string& b){
    if(a.empty()||b.empty())return false;
    std::error_code error;
    if(std::filesystem::equivalent(a,b,error)&&!error)return true;
    auto left=std::filesystem::weakly_canonical(a).wstring();
    auto right=std::filesystem::weakly_canonical(b).wstring();
#ifdef _WIN32
    for(auto& ch:left)ch=std::towlower(ch);
    for(auto& ch:right)ch=std::towlower(ch);
#endif
    return left==right;
}
inline void protect_paths(const std::string& output,const std::string& json,
                          const std::vector<std::string>& retained){
    if(same_path(output,json))throw std::invalid_argument("native output and JSON paths must differ");
    for(const auto& path:retained)if(same_path(output,path)||same_path(json,path))
        throw std::invalid_argument("native output/report must not overwrite retained input, prior result or reference");
}
inline Config configuration(Word terms,Word history,Word guards,Word requests){
    Wide input=16+Wide(8)*terms+Wide(2)*history+Wide(4)*guards+Wide(4)*requests;
    Wide output=16+input+Wide(9)*terms+Wide(4)*requests+history;
    if(!terms||input>std::numeric_limits<Word>::max()||output>std::numeric_limits<Word>::max())
        throw std::runtime_error("native representation capacity exceeds address limits");
    return {terms,history,guards,requests,Word(input),Word(output)};
}
inline std::array<Word,16> file_header(const Config& c,Word cases,Word magic){
    return {magic,1,cases,c.term_capacity,c.history_capacity_words,c.guard_capacity,
        c.request_capacity,c.case_words,c.result_words,0,0,0,0,0,0,0};
}
inline Batch load_batch(const std::string& path){
    std::ifstream stream(path,std::ios::binary|std::ios::ate);
    if(!stream)throw std::runtime_error("cannot open native input");
    const auto length=stream.tellg();stream.seekg(0);std::array<Word,16> h{};
    stream.read(reinterpret_cast<char*>(h.data()),64);
    if(!stream||h[0]!=INPUT_MAGIC||h[1]!=1||!h[2])throw std::runtime_error("invalid native file header");
    for(Word i=9;i<16;++i)if(h[i])throw std::runtime_error("nonzero native file reserved word");
    Config c=configuration(h[3],h[4],h[5],h[6]);
    if(h[7]!=c.case_words||h[8]!=c.result_words)throw std::runtime_error("native stride mismatch");
    const Wide words=Wide(h[2])*c.case_words;
    if(words>(std::numeric_limits<std::size_t>::max()-64)/4||Wide(length)!=64+4*words)
        throw std::runtime_error("native input length mismatch");
    Batch batch{c,h[2],std::vector<Word>(std::size_t(words))};
    stream.read(reinterpret_cast<char*>(batch.values.data()),std::streamsize(words*4));
    if(!stream)throw std::runtime_error("truncated native input");return batch;
}
inline void save_results(const std::string& path,const Config& c,Word cases,const std::vector<Word>& values){
    if(values.size()!=Wide(cases)*c.result_words)throw std::runtime_error("native output extent mismatch");
    AtomicOutput destination(path);auto& stream=destination.stream();
    const auto h=file_header(c,cases,OUTPUT_MAGIC);stream.write(reinterpret_cast<const char*>(h.data()),64);
    stream.write(reinterpret_cast<const char*>(values.data()),std::streamsize(values.size()*4));
    if(!stream)throw std::runtime_error("native output write failed");
    destination.publish();
}
// A resumed transaction obtains its completed-prefix obligation from an actual
// prior result, rather than trusting a newly supplied replacement for old state.
inline void validate_resume(const Batch& batch,const std::string& path){
    std::ifstream stream(path,std::ios::binary|std::ios::ate);
    if(!stream)throw std::runtime_error("cannot open native resume result");
    const auto length=stream.tellg();stream.seekg(0);std::array<Word,16> h{};
    stream.read(reinterpret_cast<char*>(h.data()),64);
    if(!stream||h[0]!=OUTPUT_MAGIC||h[1]!=1||h[2]!=batch.cases)
        throw std::runtime_error("native resume header/case count mismatch");
    for(Word i=9;i<16;++i)if(h[i])throw std::runtime_error("native resume reserved word");
    const Config prior=configuration(h[3],h[4],h[5],h[6]);
    if(h[7]!=prior.case_words||h[8]!=prior.result_words||Wide(length)!=64+Wide(4)*h[2]*prior.result_words)
        throw std::runtime_error("native resume extent mismatch");
    std::vector<Word> saved(prior.result_words),recomputed(prior.result_words);
    for(Word i=0;i<batch.cases;++i){
        stream.read(reinterpret_cast<char*>(saved.data()),std::streamsize(Wide(prior.result_words)*4));
        if(!stream)throw std::runtime_error("truncated native resume case");
        // Check the entire result against its retained proposal before trusting
        // status, committed time or history. This detects internal corruption;
        // it does not authenticate where the retained proposal originated.
        evaluate(saved.data()+original_offset(),recomputed.data(),prior);
        for(Word word=0;word<prior.result_words;++word)if(saved[word]!=recomputed[word])
            throw std::runtime_error("resume result inconsistency at case "+std::to_string(i)+
                ", word "+std::to_string(word));
        const Word* supplied=batch.values.data()+std::size_t(i)*batch.config.case_words;
        if(saved[3]>Wide(prior.history_capacity_words)*4||supplied[2]!=saved[3]||
           supplied[2]>Wide(batch.config.history_capacity_words)*4)
            throw std::runtime_error("resume completed-history length mismatch at case "+std::to_string(i));
        const Word time_offset=saved[0]?6:8;
        if(wide(supplied[6],supplied[7])!=wide(saved[16+time_offset],saved[17+time_offset]))
            throw std::runtime_error("resume completed-time mismatch at case "+std::to_string(i));
        const Word* committed=saved.data()+committed_history_offset(prior);
        const Word* old=supplied+old_history_offset(batch.config);
        for(Word byte=0;byte<supplied[2];++byte)if(byte_at(old,byte)!=byte_at(committed,byte))
            throw std::runtime_error("resume attempted to replace completed content at case "+std::to_string(i));
    }
}
inline Word number(const std::string& text){
    if(text.empty()||text[0]=='-')throw std::invalid_argument("expected unsigned integer");
    std::size_t end=0;unsigned long long n=std::stoull(text,&end,10);
    if(end!=text.size()||n>std::numeric_limits<Word>::max())throw std::invalid_argument("integer out of range");
    return Word(n);
}
inline void emit(const std::string& report,const std::string& path){
    if(!path.empty()){
        AtomicOutput destination(path);auto& out=destination.stream();
        out<<report<<'\n';destination.publish();
    }
}
} // namespace tom::native
