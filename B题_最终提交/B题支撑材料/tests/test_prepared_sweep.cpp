#include "../src/dynamic_selection.hpp"
#include <cassert>
#include <iostream>
int main(){
#ifndef B_PREPARED_SWEEP
 std::cerr<<"FAIL no reusable coverage/travel cache for repeated terminal estimates\n";return 1;
#else
 for(double angle:{0.,37.,179.5,301.}){
  auto p=geo::observe(geo::outer_disk({0,0},1500),{0,0},angle);
  p=geo::clip(p,geo::polar(1,angle),1500);
  auto h=dynamic_selection::make_hypotheses(p,{{{0,0},2,angle}},4,63);
  auto cover=adaptive_optical::cover(p,{0,0},angle);
  optical_terminal::PreparedSweep sweep(cover,h);
  uint64_t all=(uint64_t(1)<<h.size())-1;
  for(uint64_t mask:{all,uint64_t(1),all&0x5555555555555555ULL})for(auto now:{geo::Pt{0,0},geo::polar(1700,angle),geo::polar(700,angle+45)}){
   std::vector<dynamic_selection::Hypothesis> sub;for(size_t i=0;i<h.size();++i)if(mask>>i&1)sub.push_back(h[i]);
   auto route=cover;if(geo::dist(now,route.back())<geo::dist(now,route.front()))std::reverse(route.begin(),route.end());
   route=optical_order::choose(route,now,sub);
   double reference=optical_terminal::expected(route,now,sub);
   assert(std::abs(sweep.value(mask,now)-reference)<1e-8);
  }
 }
 assert(optical_terminal::update({{0,0},{1,0},{0,1}},{0,0},0).size()==3);
 for(int out=10;out<190;++out){geo::Pt q{200,-100};auto p=geo::outer_disk(q,1500);auto after=optical_terminal::update(p,q,out);
  for(double delta:{-2.004,0.,2.004})assert(geo::contains(after,q+geo::polar(1200,2*(out-10)+1+delta)));
 }
 std::cout<<"PASS cached sweep equals execution policy for rotations, masks and both entry ends; bin envelope conservative\n";
#endif
}
