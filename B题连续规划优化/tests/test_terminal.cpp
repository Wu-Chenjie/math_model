#include "../src/dynamic_selection.hpp"
#include "../src/adaptive_optical.hpp"
#include "../src/optical_order.hpp"
#include <iostream>
#include <cassert>
double expected_cost(const geo::Poly& route,geo::Pt now,const std::vector<dynamic_selection::Hypothesis>& hypotheses){
 double total=0,value=0;for(auto h:hypotheses)total+=h.weight;
 for(auto h:hypotheses){double cost=0;auto at=now;bool found=false;
  for(auto q:route){cost+=geo::dist(at,q)/5;at=q;if(geo::dist(q,h.z)<=20+1e-7){cost+=5;found=true;break;}cost+=3;}
  assert(found);value+=h.weight/total*cost;
 }return value;
}
int main(){
 using namespace dynamic_selection;
 auto p=geo::observe(geo::outer_disk({0,0},1500),{0,0},0);
 p=geo::clip(p,{1,0},1500);geo::Pt now{400,120};
 std::vector<Event> history{{{0,0},2,0}};
 auto h=make_hypotheses(p,history,4,63);
 auto route=optical_order::choose(adaptive_optical::cover(p,{0,0},0),now,h);
#ifdef B_CONTEXT_TERMINAL
 auto selected=plan(p,now,{0,0},0,history,4,0,true,1000,false,63,false,1);
#else
 auto selected=plan(p,now,{0,0},0,history,4,0,true,1000,false,63,false);
#endif
 double expected=expected_cost(route,now,h);
 if(std::abs(selected.value-expected)>1e-8){std::cerr<<"FAIL actual adaptive sweep cost="<<expected<<" planner terminal="<<selected.value<<"\n";return 1;}
 assert(!selected.available);
 std::cout<<"PASS terminal matches complete conservative adaptive sweep\n";
}
