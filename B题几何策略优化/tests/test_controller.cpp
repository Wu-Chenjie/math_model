#include "../src/simulator.hpp"
#include "../src/configurations.hpp"
#include <cassert>
#include <iostream>
int main(){
 int actions=0,plans=0;
 for(int p:{3,4})for(int stress:{0,1,2,3}){
  auto o=configuration(5);o.dynamic_depth=2;o.active_mode=p==3?1:0;
  Sim s(make_case(p,73,stress),73,stress==2?2:0);Policy b(s,p,o);b.run();
  assert(b.dynamic_plans>0);assert(s.success==s.total());assert(b.dynamic_actions<=6*s.total());assert(b.certificate!="incomplete");
  assert(std::abs(s.time-(s.length/5+s.switches+5*s.measures+3*s.miss+5*s.success))<.001);actions+=b.dynamic_actions;plans+=b.dynamic_plans;
 }
 auto o=configuration(5);o.dynamic_depth=2;o.dp_node_limit=0;Sim s(make_case(4,89),89,0);Policy b(s,4,o);b.run();assert(b.dynamic_actions==0&&b.dynamic_fallbacks>0&&s.success==s.total());
 assert(actions>0);std::cout<<"PASS controller: eight nominal/boundary/collinear/dense cases, "<<plans<<" replans and "<<actions<<" actions; zero-budget fallback\n";
}
