#include "policy.hpp"
#include "configurations.hpp"
#include <iostream>
#include <iomanip>
// Solver receives observations only; no simulator headers or case data are linked.
struct PipeSensor:Sensor {
 Reading measure(Pt p,int k)override{std::cout<<std::setprecision(17)<<"measure "<<k<<" "<<p.x<<" "<<p.y<<std::endl;Reading r;if(!(std::cin>>r.kind>>r.angle))throw std::runtime_error("bridge ended");return r;}
 bool clear(Pt p,int k)override{std::cout<<std::setprecision(17)<<"clear "<<k<<" "<<p.x<<" "<<p.y<<std::endl;int ok;if(!(std::cin>>ok))throw std::runtime_error("bridge ended");return ok==1;}
};
int main(int argc,char**argv){try{
 int prob=argc>1?atoi(argv[1]):3;if(prob!=3&&prob!=4)throw std::runtime_error("problem must be 3 or 4");
 Options o=configuration(5);if(argc>2)o.early=atof(argv[2]);if(argc>3)o.eta=atof(argv[3]);
 int depth=argc>4?std::stoi(argv[4]):2;if(depth<0||depth>3)throw std::runtime_error("planner depth must be in [0,3]");
 if(!(o.eta>=0&&o.eta<=.4))throw std::runtime_error("position error must be in [0,0.4]");
 if(o.eta==0){o.dynamic_depth=depth;o.active_mode=prob==3?1:0;}
 PipeSensor s;Policy bot(s,prob,o);bot.run();
 std::cerr<<"planner_depth="<<o.dynamic_depth<<" dp_calls="<<bot.dynamic_plans<<" dp_actions="<<bot.dynamic_actions<<" dp_fallbacks="<<bot.dynamic_fallbacks<<" budget_hits="<<bot.dp_budget_hits<<"\n";
 std::cout<<"exit "<<bot.cleared<<" "<<bot.certificate<<std::endl;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
