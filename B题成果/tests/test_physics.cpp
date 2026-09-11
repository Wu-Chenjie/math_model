#include "../src/simulator.hpp"
#include <cassert>
#include <iostream>
int main(){
 Sim s({{1,{20,0},1000,false,0},{2,{100,0},1000,true,0}},1,0);
 auto r=s.measure({0,0},1);assert(r.kind==2&&s.time==5);
 assert(s.clear({0,0},1));assert(s.time==10&&s.channel==1);
 assert(!s.clear({0,0},2));assert(s.time==13&&s.channel==1);
 assert(s.measure({0,0},2).kind==0);assert(s.time==19);
 assert(s.measure({100,1},2).kind==1);
 assert(s.clear({100,0},2));
 Sim q({{1,{1000,0},1000,false,0}},1,0);
 assert(q.measure({0,0},1).kind==2);
 assert(q.measure({-0.001,0},1).kind==0);
 auto a=q.measure({100,0},1),b=q.measure({100,0},1);assert(a.angle==b.angle);
 std::cout<<"physics checks passed\n";
}
