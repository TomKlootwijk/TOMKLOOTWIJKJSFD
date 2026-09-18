#include "tom/image.hpp"
#include <iostream>
#include <random>
#include <stdexcept>
using namespace tom;
void require(bool truth){if(!truth)throw std::runtime_error("integer core test failed");}
int main(){try{
    std::uint64_t truth_cases=0,dynamic_cases=0;
    std::mt19937 rng(20260918u);
    for(Word table=0;table<256;++table){Word a=0xaaaaaaaau,b=0xccccccccu,c=0xf0f0f0f0u;
        Word out=primitive(a,b,c,table);
        for(Word bit=0;bit<32;++bit){Word row=((a>>bit)&1u)|(((b>>bit)&1u)<<1)|(((c>>bit)&1u)<<2);require(((out>>bit)&1u)==((table>>row)&1u));++truth_cases;}}
    for(Word i=0;i<4096;++i){Word a=rng(),b=rng(),c=rng(),coeff[8];for(Word& x:coeff)x=rng();Word out=lowered(a,b,c,coeff);
        for(Word bit=0;bit<32;++bit){Word row=((a>>bit)&1u)|(((b>>bit)&1u)<<1)|(((c>>bit)&1u)<<2);require(((out>>bit)&1u)==((coeff[row]>>bit)&1u));}++dynamic_cases;}
    // Execute the actual stored canonical kernel microprogram, not just the fast path.
    std::vector<Word> atlas(16+28,0);atlas[1]=16;atlas[2]=7;atlas[3]=0xCA;atlas[4]=17;
    std::copy(CANONICAL_KERNEL.begin(),CANONICAL_KERNEL.end(),atlas.begin()+16);Header h{};h.kernel_id=0;HostReader r{atlas.data(),nullptr};
    for(Word i=0;i<4096;++i){Word a=rng(),b=rng(),c=rng(),coeff[8];for(Word& x:coeff)x=rng();require(execute_definition(r,h,a,b,c,coeff)==lowered(a,b,c,coeff));}
    // Independent minterm oracle covers every selector with arbitrary valid
    // microprogram operands, including edited bodies using canonical 0xCA.
    std::uint64_t edited_cases=0;
    for(Word selector=0;selector<256;++selector)for(Word trial=0;trial<16;++trial){
        atlas[3]=selector;Word coeff[8],local[18]{};
        for(Word i=0;i<8;++i)local[i]=coeff[i]=rng();
        Word a=local[8]=rng(),b=local[9]=rng(),c=local[10]=rng();
        for(Word step=0;step<7;++step){
            Word dst=11+step,x=rng()%dst,y=rng()%dst,z=rng()%dst;
            atlas[16+4*step]=dst;atlas[17+4*step]=x;
            atlas[18+4*step]=y;atlas[19+4*step]=z;
            Word out=0;
            for(Word row=0;row<8;++row)if((selector>>row)&1u)
                out|=(row&1u?local[x]:~local[x])&(row&2u?local[y]:~local[y])&(row&4u?local[z]:~local[z]);
            local[dst]=out;
        }
        require(execute_definition(r,h,a,b,c,coeff)==local[17]);++edited_cases;
    }
    std::cout<<"{\"status\":\"PASS\",\"all_ternary_table_lane_assertions\":"<<truth_cases<<",\"dynamic_word_cases\":"<<dynamic_cases<<",\"field_microprogram_vs_lowered_cases\":4096,\"edited_microprogram_cases\":"<<edited_cases<<",\"gpu_execution\":false}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
