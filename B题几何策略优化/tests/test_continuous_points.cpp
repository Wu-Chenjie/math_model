#include "../src/geometry.hpp"
#include <cassert>
#include <iostream>
#if __has_include("../src/continuous_points.hpp")
#include "../src/continuous_points.hpp"
#endif
int main(){
#ifndef B_CONTINUOUS_POINTS
 std::cerr<<"FAIL continuous candidate refinement is unavailable\n";return 1;
#else
 int calls=0;auto score=[&](geo::Pt q){++calls;return (q.x-37)*(q.x-37)+(q.y+23)*(q.y+23);};
 auto valid=[](geo::Pt q){return geo::norm(q)<100;};
 auto points=continuous_points::refine({{0,0},{90,0}},score,valid,80,40);
 assert(calls<=80&&!points.empty());double best=INFINITY;for(auto q:points){assert(valid(q));best=std::min(best,(q.x-37)*(q.x-37)+(q.y+23)*(q.y+23));}
 assert(best<25);auto second=continuous_points::refine({{0,0},{90,0}},score,valid,80,40);assert(second.size()==points.size());for(size_t i=0;i<points.size();++i)assert(geo::dist(second[i],points[i])==0);
 int rejected_calls=0;geo::Poly many;for(int i=0;i<100;++i)many.push_back({double(i),0});
 auto rejected=continuous_points::refine(many,[&](geo::Pt){++rejected_calls;return INFINITY;},[](geo::Pt){return true;},5,20);
 if(rejected_calls>5){std::cerr<<"FAIL nonfinite scores exceeded evaluation budget\n";return 1;}assert(rejected.empty());
 std::cout<<"PASS bounded deterministic continuous candidate refinement\n";
#endif
}
