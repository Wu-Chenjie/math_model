#include "simulator.hpp"
#include <chrono>
#include <iostream>
int main(int argc,char**argv){
 if(argc<8){std::cerr<<"experiment OUT START COUNT SPACING EARLY VARIANT STRESS [ERROR] [TRACE_PREFIX]\n";return 2;}
 std::ofstream f(argv[1]);f<<"problem,seed,variant,stress,error,total,cleared,ratio,time_s,avg_s,move_m,measures,switches,miss,fallbacks,audits,runtime_s,certificate\n";
 int start=atoi(argv[2]),count=atoi(argv[3]),variant=atoi(argv[6]),stress=atoi(argv[7]),err=argc>8?atoi(argv[8]):0;
 Options o;o.spacing=atof(argv[4]);o.early=atof(argv[5]);o.square=variant==1;o.dynamic=variant!=2;
 for(int p:{3,4})for(int seed=start;seed<start+count;++seed){
  std::string tr=argc>9?std::string(argv[9])+"_p"+std::to_string(p)+"_"+std::to_string(seed)+".csv":"";
  Sim sim(make_case(p,seed,stress),seed,err,tr);Policy bot(sim,p,o);auto begin=std::chrono::steady_clock::now();
  try{bot.run();}catch(const std::exception&e){std::cerr<<"FAIL p="<<p<<" seed="<<seed<<" "<<e.what()<<"\n";return 1;}
  double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  if(sim.success!=sim.total()||std::abs(sim.time-(sim.length/5+sim.switches+5*sim.measures+3*sim.miss+5*sim.success))>1e-3){std::cerr<<"completeness or accounting failure\n";return 1;}
  f<<std::setprecision(12)<<p<<","<<seed<<","<<variant<<","<<stress<<","<<err<<","<<sim.total()<<","<<sim.success<<",1,"<<sim.time<<","<<sim.time/sim.success<<","<<sim.length<<","<<sim.measures<<","<<sim.switches<<","<<sim.miss<<","<<bot.fallbacks<<","<<sim.audits<<","<<sec<<","<<bot.certificate<<"\n";
 }
 std::cout<<"verified "<<2*count<<" cases -> "<<argv[1]<<"\n";
}
