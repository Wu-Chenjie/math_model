#include "../src/simulator.hpp"
#include "../src/joint_config.hpp"
#include <cassert>
#include <iostream>
int main(){
 for(int p:{3,4}){auto o=configuration(5);o.dynamic_depth=2;o.active_mode=p==3?1:0;o.auxiliary=1;
  Sim s(make_case(p,73),73,0);Policy b(s,p,o);b.run();assert(b.auxiliary_calls>0);assert(s.success==s.total());assert(b.auxiliary_calls<=4*s.total());
 }
 for(int m:{12,13,14,15,16,17,18,19,20,21,22,27,32,38,39,56})for(int p:{3,4}){auto o=joint_configuration(m,p);Sim s(make_case(p,89,3),89,0);Policy b(s,p,o);b.run();assert(s.success==s.total());assert(b.dynamic_actions<=6*s.total());assert(b.auxiliary_calls<=4*s.total());}
 for(int p:{3,4})for(int stress:{0,1,2,3}){auto o=configuration(5);o.dynamic_depth=2;o.active_mode=p==3?1:0;o.auxiliary=2;o.joint_actions=true;
  Sim s(make_case(p,89,stress),89,stress==2?2:0);Policy b(s,p,o);b.run();
  assert(b.joint_steps>0&&s.success==s.total());assert(b.dynamic_actions<=6*s.total());assert(b.auxiliary_calls<=4*s.total());
  assert(b.joint_steps<=21+7*s.total());assert(std::abs(s.time-(s.length/5+s.switches+5*s.measures+3*s.miss+5*s.success))<.001);
 }
 std::cout<<"PASS auxiliary/joint progress and action limits across ten complete scenarios\n";
}
