#include "policy.hpp"
#include "configurations.hpp"
#include "joint_config.hpp"
#include "shortcut_sensor.hpp"
#include <iostream>
#include <iomanip>
// Solver receives observations only; no simulator headers or case data are linked.
struct PipeSensor:Sensor {
 Reading measure(Pt p,int k)override{std::cout<<std::setprecision(17)<<"measure "<<k<<" "<<p.x<<" "<<p.y<<std::endl;Reading r;if(!(std::cin>>r.kind>>r.angle))throw std::runtime_error("bridge ended");return r;}
 bool clear(Pt p,int k)override{std::cout<<std::setprecision(17)<<"clear "<<k<<" "<<p.x<<" "<<p.y<<std::endl;int ok;if(!(std::cin>>ok))throw std::runtime_error("bridge ended");return ok==1;}
};
int main(int argc,char**argv){try{
 int prob=argc>1?atoi(argv[1]):3;if(prob!=3&&prob!=4)throw std::runtime_error("problem must be 3 or 4");
 std::string strategy=argc>5?argv[5]:"joint";if(strategy!="joint"&&strategy!="previous"&&strategy!="baseline"&&strategy!="stage1"&&strategy!="stage2")throw std::runtime_error("strategy must be joint, previous, stage1, stage2 or baseline");
 Options o=joint_configuration(strategy=="joint"?78:strategy=="previous"?56:strategy=="stage2"?39:strategy=="stage1"?38:0,prob);if(argc>2)o.early=atof(argv[2]);if(argc>3)o.eta=atof(argv[3]);
 int depth=argc>4?std::stoi(argv[4]):2;if(depth<0||depth>3)throw std::runtime_error("planner depth must be in [0,3]");
 if(!(o.eta>=0&&o.eta<=.4))throw std::runtime_error("position error must be in [0,0.4]");
 if(o.eta==0){if(depth==0){double early=o.early;o=joint_configuration(0,prob);o.early=early;}o.dynamic_depth=depth;}
 else{double early=o.early,eta=o.eta;o=configuration(5);o.early=early;o.eta=eta;}
 PipeSensor pipe;ShortcutSensor s(pipe,o.shortcut&&o.eta==0);Policy bot(s,prob,o);bot.run();
 std::cerr<<"strategy="<<strategy<<" planner_depth="<<o.dynamic_depth<<" dp_calls="<<bot.dynamic_plans<<" dp_actions="<<bot.dynamic_actions<<" dp_fallbacks="<<bot.dynamic_fallbacks<<" budget_hits="<<bot.dp_budget_hits<<" shortcuts="<<s.shortcuts<<" saved_m="<<s.saved_distance()<<"\n";
 std::cout<<"exit "<<bot.cleared<<" "<<bot.certificate<<std::endl;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
