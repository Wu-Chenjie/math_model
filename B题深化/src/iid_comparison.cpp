#include "simulator.hpp"
#include "configurations.hpp"
#include <chrono>
#include <iostream>
int main(int argc,char**argv){std::ofstream f(argc>1?argv[1]:"iid.csv");f<<"case_id,problem,seed,n,method,cleared,time_s,avg_s,move_m,measures,switches,miss,fallbacks,runtime_s,certificate\n";
 for(int p:{3,4})for(int seed=310001;seed<310201;++seed){auto js=make_case(p,seed);for(int m=0;m<3;++m){Sim sim(js,seed,0);Policy bot(sim,p,configuration(m));auto start=std::chrono::steady_clock::now();try{bot.run();}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
  double rt=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();if(sim.success!=sim.total())return 2;
  f<<std::setprecision(13)<<seed<<","<<p<<","<<seed<<","<<sim.total()<<","<<m<<","<<sim.success<<","<<sim.time<<","<<sim.time/sim.success<<","<<sim.length<<","<<sim.measures<<","<<sim.switches<<","<<sim.miss<<","<<bot.fallbacks<<","<<rt<<","<<bot.certificate<<"\n";
 }}std::cout<<"Verified 400 IID environments / 1200 runs\n";
}
