#include "tom/native_image.hpp"
#include <iostream>
#include <iterator>

namespace {
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
std::string read(const std::filesystem::path& path){
    std::ifstream input(path,std::ios::binary);
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
void no_temporaries(const std::filesystem::path& directory){
    for(const auto& item:std::filesystem::directory_iterator(directory))
        require(item.path().filename().string().find(".tmp-")==std::string::npos,
            "unpublished temporary file was not removed");
}
}
int main(){
    const auto directory=std::filesystem::temp_directory_path()/
        ("tom-native-atomic-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    try{
        require(std::filesystem::create_directory(directory),"cannot reserve private test directory");
        const auto target=directory/"retained.tor";
        {std::ofstream initial(target,std::ios::binary);initial<<"prior completed result";}
        {
            tom::native::AtomicOutput pending(target.string());
            pending.stream()<<"unfinished replacement";
        }
        require(read(target)=="prior completed result","abandoned serialization changed prior output");
        no_temporaries(directory);
        bool failed=false;
        try{
            tom::native::AtomicOutput broken(target.string());
            broken.stream()<<"failed replacement";
            broken.stream().setstate(std::ios::badbit);
            broken.publish();
        }catch(const std::runtime_error&){failed=true;}
        require(failed,"failed output stream was published");
        require(read(target)=="prior completed result","failed serialization changed prior output");
        no_temporaries(directory);
        {
            tom::native::AtomicOutput complete(target.string());
            complete.stream()<<"new complete result";complete.publish();
        }
        require(read(target)=="new complete result","successful output did not replace prior output");
        no_temporaries(directory);
        const auto blocked=directory/"existing-directory";
        std::filesystem::create_directory(blocked);
        failed=false;
        try{
            tom::native::AtomicOutput unpublishable(blocked.string());
            unpublishable.stream()<<"cannot replace a directory";unpublishable.publish();
        }catch(const std::exception&){failed=true;}
        require(failed&&std::filesystem::is_directory(blocked),"publication failure damaged existing destination");
        no_temporaries(directory);
        tom::native::emit("{\"complete\":true}",target.string());
        require(read(target)=="{\"complete\":true}\n","atomic report serialization mismatch");
        no_temporaries(directory);
        std::filesystem::remove_all(directory);
        std::cout<<"native atomic output tests passed\n";
        return 0;
    }catch(const std::exception& error){
        std::cerr<<"native atomic output tests: "<<error.what()<<"; fixture: "<<directory<<'\n';
        return 1;
    }
}
