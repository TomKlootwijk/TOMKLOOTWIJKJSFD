#pragma once
#include "tom/core.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace tom {
constexpr std::array<Word, 28> CANONICAL_KERNEL = {
    11,0,1,8, 12,2,3,8, 13,4,5,8, 14,6,7,8,
    15,11,12,9, 16,13,14,9, 17,15,16,10
};
inline Word read_word(std::istream& in) {
    unsigned char b[4]{}; in.read(reinterpret_cast<char*>(b), 4);
    if (!in) throw std::runtime_error("truncated TOM bit image");
    return Word(b[0]) | (Word(b[1])<<8) | (Word(b[2])<<16) | (Word(b[3])<<24);
}
inline void write_word(std::ostream& out, Word x) {
    const char b[4]{char(x & 255u),char((x>>8)&255u),char((x>>16)&255u),char(x>>24)};
    out.write(b,4);
}
inline bool value_kind(Word k) {
    return k == Constant || k == State || k == Expression || k == Quote;
}
struct Image {
    Header h{};
    std::vector<Word> atlas;
    bool canonical_kernel = false;
    Word get(Word id, Word word) const {
        if (id >= h.records || word >= 16) throw std::runtime_error("definition address out of range");
        return atlas[std::size_t(id)*16 + word];
    }
    void validate() {
        if (h.magic != MAGIC || h.abi != ABI || h.record_words != 16 || !h.records ||
            h.records > (1u<<24) || !h.states || !h.scratch_slots || h.flags || h.reserved0 || h.reserved1 ||
            h.atlas_words != atlas.size() || h.atlas_words > (1u<<27) ||
            h.kernel_id >= h.records || h.time_id >= h.records)
            throw std::runtime_error("invalid TOM image header");
        auto span = [&](Wide start, Wide size) {
            if (start > atlas.size() || size > atlas.size()-start) throw std::runtime_error("image segment out of bounds");
        };
        span(0, Wide(h.records)*16);
        if (get(h.kernel_id,0) != Kernel || get(h.time_id,0) != Time)
            throw std::runtime_error("kernel/T must be declared fields");
        const Word kbase=get(h.kernel_id,1), kcount=get(h.kernel_id,2);
        if (kcount != 7 || kbase != h.records*16 || get(h.kernel_id,3)>255 || get(h.kernel_id,4)!=17)
            throw std::runtime_error("unsupported evaluator field layout");
        span(kbase,28);
        for (Word i=0;i<7;++i) {
            Word off=kbase+4*i;
            if (atlas[off]!=11+i || atlas[off+1]>=11+i || atlas[off+2]>=11+i || atlas[off+3]>=11+i)
                throw std::runtime_error("evaluator has an unavailable or future temporary");
        }
        canonical_kernel = get(h.kernel_id,3)==0xcau &&
            std::equal(CANONICAL_KERNEL.begin(), CANONICAL_KERNEL.end(),atlas.begin()+kbase);
        if (h.schedule_offset != kbase+28 || h.schedule_count > h.records)
            throw std::runtime_error("invalid schedule offset/count");
        span(h.schedule_offset,h.schedule_count);
        if (h.binding_offset != h.schedule_offset+h.schedule_count || h.bindings!=h.states ||
            get(h.time_id,1)!=h.binding_offset || get(h.time_id,2)!=h.bindings)
            throw std::runtime_error("T commit field disagrees with binding span");
        span(h.binding_offset,Wide(h.bindings)*2);
        const Wide end=Wide(h.binding_offset)+Wide(h.bindings)*2;
        if (h.atlas_words != ((end+15)&~Wide(15))) throw std::runtime_error("invalid padding extent");
        for (Wide i=end;i<h.atlas_words;++i) if (atlas[std::size_t(i)]) throw std::runtime_error("nonzero padding");
        if (h.states>h.records || h.scratch_slots>h.records) throw std::runtime_error("invalid live counts");
        std::vector<Word> seen_states(h.states,0), scheduled(h.records,0), owner(h.scratch_slots,FULL);
        for (Word id=0;id<h.records;++id) {
            Word k=get(id,0);
            if (k<Kernel || k>NativeDeclaration || get(id,14)!=id)
                throw std::runtime_error("unknown kind or missing self-reference");
            if (k==Kernel && id!=h.kernel_id) throw std::runtime_error("duplicate evaluator field");
            if (k==Time && id!=h.time_id) throw std::runtime_error("duplicate time field");
            if (k==Constant && get(id,1)>1) throw std::runtime_error("constant not one bit");
            if (k==Rule && get(id,1)>255) throw std::runtime_error("truth coefficients exceed eight bits");
            if (k==Quote && Wide(get(id,1))>=Wide(h.atlas_words)*32) throw std::runtime_error("quote exceeds image bits");
            if (k==State) {
                Word slot=get(id,1), mode=get(id,2), param=get(id,3);
                if (slot>=h.states || seen_states[slot]++ || mode>3 || (mode==2 && param>=64))
                    throw std::runtime_error("invalid state slot or seed declaration");
            }
        }
        for (Word v:seen_states) if(v!=1) throw std::runtime_error("missing state declaration");
        auto available = [&](Word id) {
            if (id>=h.records || !scheduled[id] || !value_kind(get(id,0)))
                throw std::runtime_error("unavailable dependency; use old State for temporal recursion");
            Word slot=get(id,15);
            if (slot>=h.scratch_slots || owner[slot]!=id) throw std::runtime_error("temporary value already overwritten");
        };
        for (Word n=0;n<h.schedule_count;++n) {
            Word id=atlas[h.schedule_offset+n];
            if (id>=h.records || !value_kind(get(id,0)) || scheduled[id] || get(id,15)>=h.scratch_slots)
                throw std::runtime_error("invalid scheduled declaration");
            if (get(id,0)==Expression) {
                for (Word operand=2;operand<=4;++operand) available(get(id,operand));
                Word rule=get(id,1), kind=get(rule,0);
                if (kind==DynamicRule) for (Word row=1;row<=8;++row) available(get(rule,row));
                else if(kind!=Rule) throw std::runtime_error("native role has no executable truth-table interpretation");
            }
            owner[get(id,15)]=id; scheduled[id]=1;
        }
        std::vector<Word> bound(h.states,0);
        for(Word i=0;i<h.bindings;++i) {
            Word id=atlas[h.binding_offset+2*i];
            if(get(id,0)!=State || bound[get(id,1)]++) throw std::runtime_error("invalid or repeated T state target");
            available(atlas[h.binding_offset+2*i+1]);
        }
    }
};
inline Image load_image(const std::string& path) {
    std::ifstream in(path,std::ios::binary); if(!in)throw std::runtime_error("cannot open image: "+path);
    std::array<Word,16> header{}; for(Word& v:header)v=read_word(in);
    Image p; std::memcpy(&p.h,header.data(),64);
    if(p.h.magic!=MAGIC || p.h.atlas_words>(1u<<27))throw std::runtime_error("image magic/size invalid");
    in.seekg(0,std::ios::end); auto size=in.tellg();
    if(size<0 || Wide(size)!=64+Wide(p.h.atlas_words)*4)throw std::runtime_error("file size mismatch");
    in.seekg(64);p.atlas.resize(p.h.atlas_words);for(Word& v:p.atlas)v=read_word(in);
    p.validate(); return p;
}
inline std::vector<Word> seed(const Image& p,Word words,Wide first_word=0) {
    if(!words || Wide(p.h.states)*words>FULL || first_word>(std::numeric_limits<Wide>::max()/32)-words)
        throw std::runtime_error("seed/index extent out of range");
    std::vector<Word> result(std::size_t(p.h.states)*words);
    for(Word id=0;id<p.h.records;++id) if(p.get(id,0)==State) {
        Word slot=p.get(id,1),mode=p.get(id,2),parameter=p.get(id,3);
        for(Word i=0;i<words;++i) {
            Wide global=first_word+i;Word value=0;
            if(mode==1)value=FULL;
            else if(mode==2)for(Word bit=0;bit<32;++bit)value|=Word((((global<<5)+bit)>>parameter)&1u)<<bit;
            else if(mode==3)value=seed_mix(Word(global)^Word(global>>32)^parameter);
            result[slot*words+i]=value;
        }
    }
    return result;
}
inline Wide digest(const std::vector<Word>& words) {
    Wide h=1469598103934665603ull; for(Word x:words){h^=x;h*=1099511628211ull;}return h;
}
inline void save_state(const std::string& path,const std::vector<Word>& data,Word slots,Word words,Wide epoch) {
    if(data.size()!=Wide(slots)*words)throw std::runtime_error("state extent mismatch");
    std::ofstream out(path,std::ios::binary);if(!out)throw std::runtime_error("cannot save state");
    out.write("TOM7BIT\0",8);write_word(out,slots);write_word(out,words);write_word(out,Word(epoch));write_word(out,Word(epoch>>32));
    for(Word v:data)write_word(out,v);if(!out)throw std::runtime_error("state write failed");
}
struct Data {Word slots=0,words=0;Wide epoch=0;std::vector<Word> values;};
inline Data load_state(const std::string& path) {
    std::ifstream in(path,std::ios::binary);if(!in)throw std::runtime_error("cannot open packed state");
    char magic[8]{};in.read(magic,8);if(std::memcmp(magic,"TOM7BIT\0",8))throw std::runtime_error("bad packed-state magic");
    Data d;d.slots=read_word(in);d.words=read_word(in);Word lo=read_word(in),hi=read_word(in);d.epoch=Wide(lo)|(Wide(hi)<<32);
    if(!d.slots||!d.words||Wide(d.slots)*d.words>FULL)throw std::runtime_error("packed state too large");
    in.seekg(0,std::ios::end);auto bytes=in.tellg();if(bytes<0||Wide(bytes)!=24+Wide(d.slots)*d.words*4)throw std::runtime_error("state file length mismatch");
    in.seekg(24);d.values.resize(std::size_t(d.slots)*d.words);for(Word& v:d.values)v=read_word(in);return d;
}
} // namespace tom
