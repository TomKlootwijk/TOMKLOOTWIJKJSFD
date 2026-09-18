#pragma once
// Bounded external encoding of TOM v0.7's stated native term laws.
// This executes structural normalization and a declared continuation relation.
// It does not assign the dynamics explicitly left open on source page 14.
#include "tom/core.hpp"

namespace tom::native {
constexpr Word NONE=0xffffffffu;
enum Op:Word { DECL=1,J=2,INVLOG=3,C=4,E=5,ARCH=6,INVERSE_OCCAM=7,LATER_T=8,SELF=9,FORWARD_T=10 };
enum Status:Word { INVALID=1,TEMPORAL=2,PREFIX_REWRITE=4,FUTURE_EVIDENCE=8,
    PENDING_GUARD=16,OPEN_LAW=32,UNGUARDED_RESULT=64,CAPACITY=128 };
enum Flag:Word { ALIAS_A_T=1,REQUIRE_SOURCE_TOM=2,SCALAR_LOG_ECHO=4,ADVANCE_TRANSACTION=8 };
enum RequestCode:Word { DECLARED=0,RESOLVED=1,PENDING=2,OPEN=3,UNGUARDED=4,BAD_REQUEST=5,BLOCKED_TRANSACTION=6 };
struct Config {
    Word term_capacity,history_capacity_words,guard_capacity,request_capacity,case_words,result_words;
};
TOM_HD Word terms_offset(){return 16;}
TOM_HD Word old_history_offset(const Config& c){return 16+8*c.term_capacity;}
TOM_HD Word new_history_offset(const Config& c){return old_history_offset(c)+c.history_capacity_words;}
TOM_HD Word guards_offset(const Config& c){return new_history_offset(c)+c.history_capacity_words;}
TOM_HD Word requests_offset(const Config& c){return guards_offset(c)+4*c.guard_capacity;}
TOM_HD Word original_offset(){return 16;}
TOM_HD Word normalized_offset(const Config& c){return 16+c.case_words;}
TOM_HD Word representatives_offset(const Config& c){return normalized_offset(c)+8*c.term_capacity;}
TOM_HD Word request_results_offset(const Config& c){return representatives_offset(c)+c.term_capacity;}
TOM_HD Word committed_history_offset(const Config& c){return request_results_offset(c)+4*c.request_capacity;}
TOM_HD Wide wide(Word low,Word high){return Wide(low)|(Wide(high)<<32);}
TOM_HD Word minimum(Word a,Word b){return a<b?a:b;}
TOM_HD Word arity(Word op){return (op==DECL||op==SELF)?0:((op==E||op==ARCH)?2:1);}
TOM_HD bool same_record(const Word* a,const Word* b){
    for(Word i=0;i<8;++i)if(a[i]!=b[i])return false;
    return true;
}
TOM_HD Word byte_at(const Word* data,Word byte){return (data[byte>>2]>>(8*(byte&3)))&255u;}
TOM_HD bool declaration(const Word* terms,Word id,Word symbol){
    return terms[8*id]==DECL&&terms[8*id+4]==symbol;
}
// Input has already passed bounded-reference validation. Representative ids
// use exact record equality, so shared and duplicated syntax compare identically.
TOM_HD bool is_source_tom(const Word* terms,Word root){
    const Word* p=terms+8*root;
    if(p[0]!=FORWARD_T)return false;
    p=terms+8*p[2];if(p[0]!=INVERSE_OCCAM)return false;
    p=terms+8*p[2];if(p[0]!=ARCH)return false;
    Word direct=p[2],echo=p[3];const Word* d=terms+8*direct;
    if(d[0]!=C)return false;
    d=terms+8*d[2];if(d[0]!=J||!declaration(terms,d[2],1))return false;
    const Word* e=terms+8*echo;
    if(e[0]!=E||e[2]!=direct)return false;
    const Word* inv=terms+8*e[3];
    return inv[0]==INVLOG&&declaration(terms,inv[2],2);
}

TOM_HD void evaluate(const Word* in,Word* out,const Config& c){
    // The complete original-case region is overwritten below. Do not clear it
    // first: that would perform a redundant global store for every retained word.
    for(Word i=0;i<16;++i)out[i]=0;
    for(Word i=normalized_offset(c);i<c.result_words;++i)out[i]=0;
    out[1]=NONE;
    for(Word i=0;i<c.case_words;++i)out[original_offset()+i]=in[i];
    Word* norm=out+normalized_offset(c);
    Word* reps=out+representatives_offset(c);
    Word* results=out+request_results_offset(c);
    for(Word i=0;i<c.term_capacity;++i)reps[i]=NONE;
    for(Word i=0;i<c.request_capacity;++i){results[4*i+1]=NONE;results[4*i+2]=NONE;}
    const Word count=in[0],root=in[1],old_bytes=in[2],new_bytes=in[3];
    const Word guard_count=in[4],request_count=in[5],flags=in[14];
    const Wide history_bytes=Wide(4)*c.history_capacity_words;
    const Word* terms=in+terms_offset();const Word* old=in+old_history_offset(c);
    const Word* proposed=in+new_history_offset(c);const Word* guards=in+guards_offset(c);
    const Word* requests=in+requests_offset(c);
    Word status=0;
    if(count>c.term_capacity||old_bytes>history_bytes||new_bytes>history_bytes||
       guard_count>c.guard_capacity||request_count>c.request_capacity)status|=CAPACITY;
    if(!count||root>=count||in[15]||(flags&~Word(15)))status|=INVALID;
    const Wide previous=wide(in[6],in[7]),now=wide(in[8],in[9]);
    const Wide elapsed=wide(in[10],in[11]),available=wide(in[12],in[13]);
    bool advance=(flags&ADVANCE_TRANSACTION)!=0;
    for(Word i=0;i<minimum(request_count,c.request_capacity);++i)
        if(requests[4*i+1]==1)advance=true;
    if(now<previous||(now>=previous&&elapsed!=now-previous)||(advance&&now==previous))status|=TEMPORAL;
    if(available>now)status|=FUTURE_EVIDENCE;
    bool prefix=old_bytes<=history_bytes&&new_bytes>=old_bytes&&new_bytes<=history_bytes;
    if(prefix)for(Word i=0;i<old_bytes;++i)if(byte_at(old,i)!=byte_at(proposed,i)){prefix=false;break;}
    if(!prefix)status|=PREFIX_REWRITE;
    out[6]=prefix?1:0;
    // Check every supplied record, including retained declarations not reached
    // from the selected root. Unknown instructions never become inert success.
    if(!(status&CAPACITY)){
        for(Word i=0;i<count;++i){
            const Word* p=terms+8*i;const Word op=p[0],a=p[1];
            if(op<DECL||op>FORWARD_T||a!=arity(op)||p[6]!=1||p[7]||p[5]){status|=INVALID;break;}
            if((a>=1?p[2]>=i:p[2]!=NONE)||(a>=2?p[3]>=i:p[3]!=NONE)){status|=INVALID;break;}
            if(op==DECL||op==SELF){
                if(!p[4]||(p[4]>12&&p[4]<256)){status|=INVALID;break;}
            }else if(op!=LATER_T&&p[4]){status|=INVALID;break;}
        }
        for(Word i=0;i<guard_count;++i){
            const Word* g=guards+4*i;
            if(g[1]>1||g[3]||(g[2]!=NONE&&g[2]>=count))status|=INVALID;
            for(Word j=0;j<i;++j)if(guards[4*j]==g[0])status|=INVALID;
        }
        for(Word i=0;i<request_count;++i){
            const Word* q=requests+4*i;
            if(q[0]>=count||q[1]>1||q[2]||q[3])status|=INVALID;
        }
    }
    if(!(status&(INVALID|CAPACITY))){
        out[2]=count;
        for(Word i=0;i<count;++i){
            const Word* source=terms+8*i;Word* p=norm+8*i;
            for(Word k=0;k<8;++k)p[k]=source[k];
            if(p[1]>=1)p[2]=reps[p[2]];
            if(p[1]>=2)p[3]=reps[p[3]];
            if(p[0]==DECL&&p[4]==12&&(flags&ALIAS_A_T)){p[4]=1;++out[9];}
            if(p[0]==INVERSE_OCCAM&&norm[8*p[2]]==INVERSE_OCCAM){
                const Word child=p[2];for(Word k=0;k<8;++k)p[k]=norm[8*child+k];++out[8];
            }
            Word representative=i;
            for(Word j=0;j<i;++j)if(same_record(p,norm+8*j)){representative=reps[j];break;}
            reps[i]=representative;
        }
        // Native SDF admission also requires the operand roles declared on p.5.
        // Arity alone cannot turn E(T,phi) into the specified causal echo.
        for(Word i=0;i<count;++i){
            const Word* p=norm+8*i;
            if(p[0]==J&&!declaration(norm,p[2],1))status|=INVALID;
            if(p[0]==INVLOG&&!declaration(norm,p[2],2))status|=INVALID;
            if(p[0]==E){
                const Word* inverse=norm+8*p[3];
                if(norm[8*p[2]]!=C||inverse[0]!=INVLOG||!declaration(norm,inverse[2],2))status|=INVALID;
            }
        }
        out[1]=reps[root];out[7]=is_source_tom(norm,out[1])?1:0;
        if((flags&REQUIRE_SOURCE_TOM)&&!out[7])status|=INVALID;
        // Exact theorem for the explicitly selected external scalar reading.
        // The native operands remain intact; no numerical log approximation.
        out[10]=((flags&SCALAR_LOG_ECHO)&&out[7])?1:0;
        for(Word i=0;i<request_count;++i){
            const Word* q=requests+4*i;Word* r=results+4*i;
            r[1]=reps[q[0]];const Word* term=norm+8*r[1];
            if(q[1]==0){r[0]=DECLARED;continue;}
            if(term[0]!=LATER_T){r[0]=UNGUARDED;status|=UNGUARDED_RESULT;++out[5];continue;}
            const Word* found=nullptr;
            for(Word j=0;j<guard_count;++j)if(guards[4*j]==term[4]){found=guards+4*j;break;}
            if(!found||!found[1]){r[0]=PENDING;status|=PENDING_GUARD;++out[5];continue;}
            if(found[2]==NONE){r[0]=OPEN;status|=OPEN_LAW;++out[5];continue;}
            r[0]=RESOLVED;r[2]=reps[found[2]];++out[4];
        }
    }else{
        for(Word i=0;i<minimum(request_count,c.request_capacity);++i)results[4*i]=BAD_REQUEST;
    }
    if(status&&out[4]){
        for(Word i=0;i<minimum(request_count,c.request_capacity);++i)
            if(results[4*i]==RESOLVED){results[4*i]=BLOCKED_TRANSACTION;++out[5];}
        out[4]=0;
    }
    // Commit only a fully admitted supplied extension. Rejected or unresolved
    // transactions retain the original complete prefix without ring overwrite.
    const Word kept=status?(Wide(old_bytes)<history_bytes?old_bytes:Word(history_bytes)):new_bytes;
    const Word* history=status?old:proposed;Word* committed=out+committed_history_offset(c);
    for(Word i=0;i<(Wide(kept)+3)/4;++i)committed[i]=history[i];
    if(kept&3)committed[kept/4]&=(Word(1)<<(8*(kept&3)))-1;
    out[0]=status;out[3]=kept;
}
} // namespace tom::native
