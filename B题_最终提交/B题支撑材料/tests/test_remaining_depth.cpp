#include "../src/dynamic_selection.hpp"
#include <iostream>
#include <cassert>
int main(){
#ifdef B_REMAINING_DEPTH
 int depth=dynamic_selection::remaining_depth(2,6,5);
#else
 int depth=2;
#endif
 belief_dp::Model m;m.weights={1,1};m.actions={{true,{10,11},{5,5}},{false,{-1,0},{5,3}},{false,{0,-1},{3,5}}};m.travel.assign(4,std::vector<double>(4));
 m.travel[3][1]=m.travel[3][2]=15;
 m.terminal=[](uint64_t mask,int){return mask==3?100.:50.;};
 auto r=belief_dp::solve(m,depth,false,1000);
 if(r.action==0){std::cerr<<"FAIL final allowed action relies on a second dynamic action\n";return 1;}
#ifdef B_REMAINING_DEPTH
 assert(depth==1);assert(dynamic_selection::remaining_depth(3,6,6)==0);assert(dynamic_selection::remaining_depth(2,6,0)==2);
 assert(belief_dp::solve(m,2,false,1000).action==0);
#endif
 std::cout<<"PASS Bellman horizon respects remaining dynamic action allowance\n";
}
