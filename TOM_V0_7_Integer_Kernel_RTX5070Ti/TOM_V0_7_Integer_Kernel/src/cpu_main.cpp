#include "tom/cli.hpp"
int main(int argc,char** argv) {
    using namespace tom;
    try {
        Options o=options(argc,argv);if(o.help){usage(false);return 0;}
        if(o.info||o.verify||o.percent)throw std::invalid_argument("GPU info/verify/VRAM options belong to tom_cuda; run the test suite for CPU verification");
        if(o.program.empty())throw std::invalid_argument("--program required");
        Image p=load_image(o.program);check_evaluator(p,o);
        Data input;
        if(!o.data.empty()){
            input=load_state(o.data);if(input.slots!=p.h.states)throw std::runtime_error("program/data signal counts differ");
            if(o.lanes_given&&o.lanes!=Wide(input.words)*32)throw std::runtime_error("explicit lanes and packed data count differ");
            o.lanes=Wide(input.words)*32;
        } else {
            Wide words=o.lanes/32;
            if(words>FULL||words*std::max(p.h.states,p.h.scratch_slots)>FULL)throw std::runtime_error("single CPU batch address range exceeded");
            input={p.h.states,Word(words),0,seed(p,Word(words))};
        }
        if(Wide(input.words)*p.h.scratch_slots>FULL)throw std::runtime_error("scratch address extent exceeded");
        if(input.epoch>std::numeric_limits<Wide>::max()-o.ticks)throw std::runtime_error("epoch would wrap; elapsed order cannot silently reset");
        std::vector<Word> scratch(std::size_t(p.h.scratch_slots)*input.words),next(input.values.size());
        Trace trace(o.trace,p.h.states,input.words,input.epoch,Wide(o.ticks)+1);trace.append(input.values);
        auto begin=std::chrono::steady_clock::now();
        for(Word n=0;n<o.ticks;++n){cpu_tick(p,input.values,scratch,next,input.words,o.evaluator=="lowered");input.values.swap(next);trace.append(input.values);}
        auto end=std::chrono::steady_clock::now();input.epoch+=o.ticks;
        if(!o.output.empty())save_state(o.output,input.values,p.h.states,input.words,input.epoch);
        std::ostringstream r;r<<"{\n\"name\":\"TOM\",\"version\":\"0.7-K1\",\"backend\":\"cpu\",\"evaluator\":\""<<o.evaluator<<"\",\n"
          <<"\"lanes\":"<<o.lanes<<",\"ticks\":"<<o.ticks<<",\"epoch\":"<<input.epoch<<",\"states\":"<<p.h.states<<",\"scratch_slots\":"<<p.h.scratch_slots<<",\n"
          <<"\"definition_bytes\":"<<p.atlas.size()*4<<",\"working_bytes\":"<<(Wide(2)*p.h.states+p.h.scratch_slots)*input.words*4<<",\n"
          <<"\"elapsed_host_ns\":"<<std::chrono::duration_cast<std::chrono::nanoseconds>(end-begin).count()<<",\"output_digest\":"<<digest(input.values)<<",\n"
          <<"\"trace_io_in_timing\":"<<(trace.enabled()?"true":"false")<<",\"gpu_executed\":false,\"source_physics_validated\":false\n}";
        emit(r.str(),o.json);return 0;
    } catch(const std::exception& e){std::cerr<<"tom_cpu: "<<e.what()<<'\n';return 1;}
}
