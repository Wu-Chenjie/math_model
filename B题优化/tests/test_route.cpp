#include "../src/routing.hpp"
#include <cassert>
#include <iostream>
int main(){
 geo::Poly p={{10,0},{0,10},{10,10},{20,0},{20,10}};
 auto old=route::nearest({0,0},p);
 auto r=route::optimize({0,0},p);
 assert(r.size()==p.size());auto sorted=r;std::sort(sorted.begin(),sorted.end());
 for(size_t i=0;i<p.size();++i)assert(sorted[i]==(int)i);
 assert(route::length({0,0},p,r)<=route::length({0,0},p,old)+1e-8);
 assert(route::optimize({0,0},{}).empty());
 std::vector<int> crossed={0,1,2,3,4};double before=route::length({0,0},p,crossed);
 route::two_opt({0,0},p,crossed);assert(route::length({0,0},p,crossed)<=before+1e-8);
 std::cout<<"route tests passed\n";
}
