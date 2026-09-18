#include "tom/native_image.hpp"
#include <iostream>
int main(int argc,char** argv){
    using namespace tom;using namespace tom::native;
    try{
        std::string input,output,json,resume;Word repeat=1;
        for(int i=1;i<argc;++i){std::string a=argv[i];
            if(a=="--help"){std::cout<<"--input FILE --output FILE --resume PRIOR_RESULTS --repeat N --json FILE\n";return 0;}
            if(i+1==argc)throw std::invalid_argument("option value missing");std::string v=argv[++i];
            if(a=="--input")input=v;else if(a=="--output")output=v;
            else if(a=="--resume")resume=v;
            else if(a=="--json")json=v;else if(a=="--repeat")repeat=number(v);
            else throw std::invalid_argument("unknown native CPU option: "+a);
        }
        if(input.empty()||!repeat)throw std::invalid_argument("input and positive repeat required");
        protect_paths(output,json,{input,resume});
        Batch b=load_batch(input);if(!resume.empty())validate_resume(b,resume);
        std::vector<Word> result(std::size_t(b.cases)*b.config.result_words);
        const auto begin=std::chrono::steady_clock::now();
        for(Word r=0;r<repeat;++r)for(Word i=0;i<b.cases;++i)
            evaluate(b.values.data()+std::size_t(i)*b.config.case_words,
                result.data()+std::size_t(i)*b.config.result_words,b.config);
        const auto end=std::chrono::steady_clock::now();
        if(!output.empty())save_results(output,b.config,b.cases,result);
        Wide admitted=0,source=0,rewrites=0;
        for(Word i=0;i<b.cases;++i){const Word* p=result.data()+std::size_t(i)*b.config.result_words;
            admitted+=p[0]==0;source+=p[7]!=0;rewrites+=p[8];}
        std::ostringstream report;report<<"{\"backend\":\"native_cpu\",\"gpu_executed\":false,\"cases\":"<<b.cases
            <<",\"resume_validated\":"<<(resume.empty()?"false":"true")
            <<",\"repeat\":"<<repeat<<",\"admitted\":"<<admitted<<",\"source_TOM\":"<<source
            <<",\"preservation_rewrites\":"<<rewrites<<",\"elapsed_ns\":"
            <<std::chrono::duration_cast<std::chrono::nanoseconds>(end-begin).count()
            <<",\"unique_dynamics_assigned\":false}";
        std::cout<<report.str()<<'\n';emit(report.str(),json);return 0;
    }catch(const std::exception& e){std::cerr<<"tom_native_cpu: "<<e.what()<<'\n';return 1;}
}
