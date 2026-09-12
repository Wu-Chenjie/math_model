#include "simulator.hpp"
#include "configurations.hpp"
#include <chrono>
#include <iostream>
int main(int argc,char**argv){if(argc<4)return 2;int start=atoi(argv[2]),count=atoi(argv[3]);std::ofstream f(argv[1]);f<<"problem,seed,method,n,cleared,time_s,avg_s,move_m,measures,switches,miss,fallbacks,plans,exact_plans,local_plans,nonlocal_plans,max_route_gap_m,mean_route_gap_m,weighted_gap_ratio,max_relative_gap,skipped,runtime_s,certificate\n";
 for(int p:{3,4})for(int seed=start;seed<start+count;++seed){auto js=make_case(p,seed);for(int m=0;m<6;++m){Sim sim(js,seed,0);Policy bot(sim,p,configuration(m));auto begin=std::chrono::steady_clock::now();try{bot.run();}catch(const std::exception&e){std::cerr<<"FAIL "<<p<<" "<<seed<<" "<<m<<" "<<e.what()<<"\n";return 1;}
  if(sim.success!=sim.total())return 3;double rt=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  f<<std::setprecision(13)<<p<<","<<seed<<","<<m<<","<<sim.total()<<","<<sim.success<<","<<sim.time<<","<<sim.time/sim.success<<","<<sim.length<<","<<sim.measures<<","<<sim.switches<<","<<sim.miss<<","<<bot.fallbacks<<","<<bot.plans<<","<<bot.exact_plans<<","<<bot.local_plans<<","<<bot.nonlocal_plans<<","<<bot.max_route_gap<<","<<(bot.plans?bot.total_route_gap/bot.plans:0)<<","<<(bot.total_route_upper?bot.total_route_gap/bot.total_route_upper:0)<<","<<bot.max_relative_gap<<","<<bot.covered_skips<<","<<rt<<","<<bot.certificate<<"\n";
 }}std::cout<<"Verified "<<2*count<<" environments and "<<12*count<<" runs\n";
}
