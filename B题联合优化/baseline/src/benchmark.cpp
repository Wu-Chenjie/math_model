#include "simulator.hpp"
#include "configurations.hpp"
#include <chrono>
#include <iostream>
Options benchmark_options(int method,int problem){auto o=configuration(5);if(method>=1)o.active_mode=problem==3?1:0;if(method>=2)o.dynamic_depth=method-1;return o;}
int main(int argc,char**argv){
 if(argc<4){std::cerr<<"benchmark OUTPUT START COUNT [STRESS] [LAST_METHOD]\n";return 2;}
 int start=atoi(argv[2]),count=atoi(argv[3]),stress=argc>4?atoi(argv[4]):0,last=argc>5?atoi(argv[5]):3;
 if(count<1||start<1||last<0||last>4||stress<0||stress>5)return 2;
 std::ofstream f(argv[1]);if(!f)return 2;
 f<<"problem,seed,method,stress,n,cleared,time_s,avg_s,move_m,measures,switches,miss,fallbacks,dp_calls,dp_actions,dp_fallbacks,dp_expanded,dp_budget_hits,runtime_s,certificate\n";
 for(int prob:{3,4})for(int seed=start;seed<start+count;++seed){auto environment=make_case(prob,seed,stress);
  for(int method=0;method<=last;++method){auto options=benchmark_options(method,prob);Sim sim(environment,seed,stress==2?2:stress==4?3:stress==5?4:0);Policy bot(sim,prob,options);
   auto begin=std::chrono::steady_clock::now();
   try{bot.run();if(sim.success!=sim.total())throw std::runtime_error("incomplete");if(bot.dynamic_actions>6*sim.total())throw std::runtime_error("dynamic action limit");
    double cost=sim.length/5+sim.switches+5*sim.measures+3*sim.miss+5*sim.success;if(std::abs(sim.time-cost)>.001)throw std::runtime_error("accounting");}
   catch(const std::exception&e){std::cerr<<"FAIL problem="<<prob<<" seed="<<seed<<" method="<<method<<" "<<e.what()<<std::endl;return 1;}
   double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
   f<<std::setprecision(13)<<prob<<","<<seed<<","<<method<<","<<stress<<","<<sim.total()<<","<<sim.success<<","<<sim.time<<","<<sim.time/sim.total()<<","<<sim.length<<","<<sim.measures<<","<<sim.switches<<","<<sim.miss<<","<<bot.fallbacks<<","<<bot.dynamic_plans<<","<<bot.dynamic_actions<<","<<bot.dynamic_fallbacks<<","<<bot.dp_expanded<<","<<bot.dp_budget_hits<<","<<seconds<<","<<bot.certificate<<"\n";
  }
  if((seed-start+1)%10==0){f.flush();std::cout<<"p="<<prob<<" cases="<<seed-start+1<<std::endl;}
 }
}
