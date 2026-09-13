#include "simulator.hpp"
#include "configurations.hpp"
#include <iostream>
struct Profile:Sim {int stage=0;double times[3]{},moves[3]{};int counts[3]{};
 using Sim::Sim;void phase(int p)override{stage=p;}
 Reading measure(Pt p,int k)override{double before=time,d=length;auto r=Sim::measure(p,k);times[stage]+=time-before;moves[stage]+=length-d;++counts[stage];return r;}
 bool clear(Pt p,int k)override{double before=time,d=length;auto r=Sim::clear(p,k);times[stage]+=time-before;moves[stage]+=length-d;++counts[stage];return r;}
};
int main(){std::ofstream out("results/profile.csv");out<<"problem,seed,total,scan,local,optical,scan_move,local_move,optical_move,scan_actions,local_actions,optical_actions\n";
 for(int p:{3,4})for(int seed=1;seed<=40;++seed){auto o=configuration(5);o.dynamic_depth=2;o.active_mode=p==3?1:0;Profile s(make_case(p,seed),seed,0);Policy b(s,p,o);b.run();if(s.success!=s.total())return 1;
  out<<std::setprecision(13)<<p<<","<<seed<<","<<s.time;for(auto v:s.times)out<<","<<v;for(auto v:s.moves)out<<","<<v;for(auto v:s.counts)out<<","<<v;out<<"\n";
 }std::cout<<"profiled 80 baseline cases\n";
}
