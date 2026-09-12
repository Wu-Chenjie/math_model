#include "../src/dynamic_selection.hpp"
#include <cassert>
#include <iostream>
int main(){
 using namespace dynamic_selection;
 Hypothesis omni{{500,0},1000,false,0,1},left{{500,0},1000,true,180,1};
 std::vector<Event>history{{{0,0},2,0},{{1000,0},0,0}};
 assert(consistent(left,history));assert(!consistent(omni,history));
 history.back().q={2000,0};assert(consistent(omni,history));
 history.push_back({{490,0},3,0});assert(!consistent(omni,history));
 assert(consistent(omni,{{{496,0},1,0}}));assert(!consistent(omni,{{{496,0},2,0}}));
 assert(consistent(omni,{{{1000,0},2,180}}));assert(!consistent(omni,{{{1000,0},2,0}}));
 auto p=geo::observe(geo::outer_disk({0,0},1500),{0,0},0);p=geo::clip(p,{1,0},1500);auto original=p;
 history={{{0,0},2,0},{{1000,0},0,0}};
 auto hypotheses=make_hypotheses(p,history,4,32);assert(!hypotheses.empty()&&hypotheses.size()<=32);
 for(auto h:hypotheses){assert(geo::contains(p,h.z));assert(consistent(h,history));}
 auto choice=plan(p,{0,0},{0,0},0,history,4,1,true,2000);
 assert(choice.available&&choice.depth==1&&choice.hypotheses>0);
 assert(std::isfinite(choice.value)&&geo::norm(choice.point)<2672);
 if(choice.measure)for(auto e:history)if(e.kind<=2)assert(geo::dist(e.q,choice.point)>1e-6);
 assert(p.size()==original.size());for(size_t i=0;i<p.size();++i)assert(geo::dist(p[i],original[i])==0);
 auto exhausted=plan(p,{0,0},{0,0},0,history,4,2,true,0);assert(!exhausted.available&&exhausted.budget_hit);
 assert(make_hypotheses({},history,3,32).empty());
 std::cout<<"PASS selection: reception, direction, no-signal/near, failed clear, support, no repeats, polygon isolation and budget\n";
}
