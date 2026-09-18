#pragma once
#include "tom/image.hpp"
#include <charconv>
#include <chrono>
#include <iostream>
#include <sstream>
namespace tom {
struct Options {
    std::string program, data, output, json, trace, state_mask_out, backend="texture", evaluator="field";
    Wide lanes=65536;
    Word ticks=1, warmup=0, percent=0, block=128, shard_words=0, blocks_per_sm=8;
    std::vector<Word> count_states;
    unsigned device=0;
    Word state_mask_slot=0;
    bool help=false,info=false,verify=false,lanes_given=false,state_mask_slot_given=false;
};
inline Wide number(const std::string& text) {
    Wide result=0;auto parsed=std::from_chars(text.data(),text.data()+text.size(),result);
    if(parsed.ec!=std::errc()||parsed.ptr!=text.data()+text.size())throw std::invalid_argument("unsigned integer required: "+text);
    return result;
}
inline Word number32(const std::string& s){Wide n=number(s);if(n>FULL)throw std::invalid_argument("uint32 overflow");return Word(n);}
inline Options options(int argc,char** argv) {
    Options o;
    for(int i=1;i<argc;++i) {
        std::string a=argv[i];
        if(a=="--help"||a=="-h"){o.help=true;continue;}
        if(a=="--info"){o.info=true;continue;}
        if(a=="--verify"){o.verify=true;continue;}
        if(i+1>=argc)throw std::invalid_argument("missing option value: "+a);
        std::string v=argv[++i];
        if(a=="--program")o.program=v;else if(a=="--data")o.data=v;
        else if(a=="--out")o.output=v;else if(a=="--json")o.json=v;else if(a=="--trace")o.trace=v;
        else if(a=="--backend")o.backend=v;else if(a=="--evaluator")o.evaluator=v;
        else if(a=="--lanes"){o.lanes=number(v);o.lanes_given=true;}
        else if(a=="--ticks")o.ticks=number32(v);else if(a=="--warmup")o.warmup=number32(v);else if(a=="--vram-percent")o.percent=number32(v);
        else if(a=="--device"){Word d=number32(v);if(d>2147483647u)throw std::invalid_argument("device index range");o.device=d;}
        else if(a=="--block")o.block=number32(v);
        else if(a=="--shard-words")o.shard_words=number32(v);
        else if(a=="--blocks-per-sm")o.blocks_per_sm=number32(v);
        else if(a=="--count-state"){Word slot=number32(v);if(std::find(o.count_states.begin(),o.count_states.end(),slot)==o.count_states.end())o.count_states.push_back(slot);}
        else if(a=="--state-mask-out")o.state_mask_out=v;
        else if(a=="--state-mask-slot"){o.state_mask_slot=number32(v);o.state_mask_slot_given=true;}
        else throw std::invalid_argument("unknown option: "+a);
    }
    if(o.evaluator!="field"&&o.evaluator!="lowered")throw std::invalid_argument("evaluator must be field or lowered");
    if(o.backend!="texture"&&o.backend!="global"&&o.backend!="shared")throw std::invalid_argument("backend must be texture, global or shared");
    if(!o.lanes||(o.lanes&31u)||o.lanes>(std::numeric_limits<Wide>::max()>>1))throw std::invalid_argument("lanes must be positive multiple of 32 in supported range");
    if(o.percent>100)throw std::invalid_argument("vram-percent must be 0..100");
    if(o.block!=64&&o.block!=128&&o.block!=256)throw std::invalid_argument("block must be 64,128 or256");
    if(!o.blocks_per_sm||o.blocks_per_sm>1024)throw std::invalid_argument("blocks-per-sm must be 1..1024");
    if((!o.state_mask_out.empty())!=o.state_mask_slot_given)throw std::invalid_argument("state-mask-out and state-mask-slot must be supplied together");
    if(!o.data.empty()&&o.percent)throw std::invalid_argument("vram-percent is for generated batches; explicit data retains its own case count");
    return o;
}
inline std::string escape(const std::string& s) {
    std::string out;
    for(unsigned char c:s){if(c=='"'||c=='\\')out+='\\';if(c>=32)out+=char(c);}
    return out;
}
inline void emit(const std::string& text,const std::string& path) {
    std::cout<<text<<'\n';
    if(!path.empty()){std::ofstream f(path);if(!f)throw std::runtime_error("cannot write report");f<<text<<'\n';}
}
inline void usage(bool gpu) {
    std::cout<<"TOM V0.7 integer validation realization K1\n"
      <<"--program IMAGE.tsdf [--data INPUT.tsdf] --ticks N --lanes MULTIPLE_OF_32\n"
      <<"--evaluator field|lowered --out RESULT.tsdf --trace TRACE.ttrace --json REPORT.json\n";
    if(gpu)std::cout<<"--backend texture|global|shared --block 64|128|256 --warmup UNTIMED_TICKS --vram-percent 0..100 --device N --info --verify\n";
    if(gpu)std::cout<<"--shard-words CAP (0=automatic) --blocks-per-sm 1..1024 --count-state SLOT (repeatable, all-shard Boolean totals)\n";
    if(gpu)std::cout<<"--state-mask-out PATH --state-mask-slot SLOT (one Boolean plane across all shards)\n";
}
inline void check_evaluator(const Image& p,const Options& o){if(o.evaluator=="lowered"&&!p.canonical_kernel)throw std::runtime_error("lowering would ignore an edited kernel definition; use --evaluator field");}
class Trace {
    std::ofstream out_;
    std::size_t frame_words_=0;
public:
    Trace(const std::string& path,Word states,Word words,Wide initial_epoch,Wide frames) {
        if(path.empty())return;
        out_.open(path,std::ios::binary);if(!out_)throw std::runtime_error("cannot open trace");
        out_.write("TOM7TRC\0",8);write_word(out_,states);write_word(out_,words);
        write_word(out_,Word(initial_epoch));write_word(out_,Word(initial_epoch>>32));
        write_word(out_,Word(frames));write_word(out_,Word(frames>>32));
        frame_words_=std::size_t(states)*words;
    }
    bool enabled()const{return out_.is_open();}
    void append(const std::vector<Word>& state) {
        if(!enabled())return;
        if(state.size()!=frame_words_)throw std::runtime_error("trace frame size mismatch");
        for(Word v:state)write_word(out_,v);
        if(!out_)throw std::runtime_error("trace write failed");
    }
};
inline void cpu_tick(const Image& p,const std::vector<Word>& old,std::vector<Word>& scratch,
                     std::vector<Word>& next,Word words,bool lower) {
    HostReader r{p.atlas.data(),old.data()};
    for(Word i=0;i<words;++i) {
        if(lower)transition<true>(r,scratch.data(),next.data(),p.h,words,i);
        else transition<false>(r,scratch.data(),next.data(),p.h,words,i);
    }
}
}
