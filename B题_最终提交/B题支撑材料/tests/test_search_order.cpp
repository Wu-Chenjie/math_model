#include "../src/optical_order.hpp"
#include "../src/optical_terminal.hpp"
#include <cassert>
#include <iostream>
int main(){geo::Poly p{{100,0},{1000,0},{-100,0},{-1000,0},{0,0}};geo::Pt now{0,50};
 std::vector<dynamic_selection::Hypothesis> h;for(auto q:p)h.push_back({q,1000,false,0,q.x==0?10.:1.});
 auto old=optical_order::choose(p,now,h);
#ifdef B_SEARCH_ORDER
 auto improved=optical_order::search(p,now,h,0);
#else
 auto improved=old;
#endif
 double before=optical_terminal::expected(old,now,h),after=optical_terminal::expected(improved,now,h);
 if(after>=before-1){std::cerr<<"FAIL search order expected cost "<<after<<" did not beat cyclic "<<before<<"\n";return 1;}
#ifdef B_SEARCH_ORDER
 for(double mix:{0.,.1,.3}){auto q=optical_order::search(p,now,h,mix);assert(q.size()==p.size());for(auto v:p){int count=0;for(auto z:q)count+=geo::dist(z,v)<1e-8;assert(count==1);}}
 assert(optical_order::search({},now,h,0).empty());
 assert(optical_order::search(p,now,{},0).size()==p.size());
#endif
 std::cout<<"PASS probability-per-time search improves cyclic route and preserves every cover center\n";
}
