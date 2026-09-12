#include "../src/optical_terminal.hpp"
#if __has_include("../src/optical_portfolio.hpp")
#include "../src/optical_portfolio.hpp"
#endif
#include <iostream>
#include <cassert>
int main(){
#ifndef B_OPTICAL_PORTFOLIO
 std::cerr<<"FAIL optical replacement lacks a minimum modeled saving guard\n";return 1;
#else
 geo::Poly old{{100,0},{1000,0},{0,0}},candidate{{0,0},{100,0},{1000,0}};geo::Pt now{0,0};
 std::vector<dynamic_selection::Hypothesis> h{{{0,0},1000,false,0,1}};
 auto chosen=optical_portfolio::choose(old,candidate,now,h,.1,10);assert(chosen.size()==candidate.size()&&geo::dist(chosen.front(),{0,0})==0);
 auto retained=optical_portfolio::choose(candidate,old,now,h,.1,10);assert(geo::dist(retained.front(),{0,0})==0);
 auto guarded=optical_portfolio::choose(old,candidate,now,h,.99,10000);assert(geo::dist(guarded.front(),old.front())==0);
 assert(optical_portfolio::choose(old,candidate,now,{},0,0).size()==old.size());
 std::cout<<"PASS optical portfolio keeps incumbent unless modeled improvement exceeds guard\n";
#endif
}
