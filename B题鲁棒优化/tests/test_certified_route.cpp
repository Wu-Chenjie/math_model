#include "../src/certified_route.hpp"
#include <cassert>
#include <numeric>
#include <iostream>
int main(){
 cert_route::Problem p;p.start={4,2,9,3};p.edge={{0,3,7,2},{8,0,2,4},{6,5,0,1},{3,6,4,0}};
 std::vector<int>r(4);std::iota(r.begin(),r.end(),0);double best=1e99;
 do{best=std::min(best,cert_route::length(p,r));}while(std::next_permutation(r.begin(),r.end()));
 auto sol=cert_route::solve(p);assert(sol.exact);assert(std::abs(sol.upper-best)<1e-8);assert(sol.lower<=best+1e-8);
 p.start.assign(15,1);p.edge.assign(15,std::vector<double>(15,1));for(int i=0;i<15;++i)p.edge[i][i]=0;
 sol=cert_route::solve(p);assert(sol.path.size()==15);assert(sol.lower<=sol.upper+1e-8);assert(sol.local_optimal);
 std::cout<<"certified route tests passed\n";
}
