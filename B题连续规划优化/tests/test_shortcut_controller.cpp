#include "../src/simulator.hpp"
#include "../src/joint_config.hpp"
#include "../src/shortcut_sensor.hpp"
#include <cassert>
#include <iostream>
struct EventProbe:Sim{
 struct Record{int kind,k,result;geo::Pt q;double angle;};std::vector<Record>events;using Sim::Sim;
 Reading measure(geo::Pt q,int k)override{auto r=Sim::measure(q,k);events.push_back({0,k,r.kind,q,r.angle});return r;}
 bool clear(geo::Pt q,int k)override{auto r=Sim::clear(q,k);events.push_back({1,k,int(r),q,0});return r;}
};
int main(){
#ifndef B_SHORTCUT_CONFIG
 std::cerr<<"FAIL shortcut strategy not integrated with the frozen controller\n";return 1;
#else
 int stopped=0;double savings=0;
 for(int problem:{3,4})for(int stress=0;stress<=5;++stress){int seed=2140001+stress;
  auto environment=make_case(problem,seed,stress);int error=stress==2?2:stress==4?3:stress==5?4:0;
  EventProbe baseline(environment,seed,error),candidate(environment,seed,error);
  Policy old(baseline,problem,joint_configuration(56,problem));old.run();
  auto options=joint_configuration(78,problem);assert(options.shortcut);ShortcutSensor io(candidate);Policy improved(io,problem,options);improved.run();
  assert(baseline.total()==baseline.success&&candidate.total()==candidate.success);
  assert(baseline.events.size()==candidate.events.size());
  for(size_t i=0;i<baseline.events.size();++i){auto a=baseline.events[i],b=candidate.events[i];assert(a.kind==b.kind&&a.k==b.k&&a.result==b.result);
   if(a.kind==0){assert(a.q.x==b.q.x&&a.q.y==b.q.y);assert(a.angle==b.angle);}
  }
  assert(candidate.time<=baseline.time+1e-4);assert(std::abs(baseline.length-candidate.length-io.saved_distance())<1e-5);
  assert(old.dynamic_plans==improved.dynamic_plans&&old.dynamic_actions==improved.dynamic_actions);
  stopped+=io.shortcuts;savings+=baseline.time-candidate.time;
 }
 assert(stopped>0&&savings>0);std::cout<<"PASS shortcut controller: 12 matched nominal/stress traces; "<<stopped<<" shortcuts, "<<savings<<" seconds saved\n";
#endif
}
