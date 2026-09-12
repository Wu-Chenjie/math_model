#include "../src/simulator.hpp"
#include "../src/configurations.hpp"
#include <cassert>
#include <iostream>
int main(){auto o=configuration(5);o.q3_radius=1124;Sim s({},1,0);Policy b(s,3,o);auto pts=b.covering_points();assert(pts.size()==7);assert(std::abs(geo::norm(pts[1])-1124)<1e-8);
 for(int k=0;k<=60;++k)for(int j=0;j<720;++j){auto z=geo::polar(30*k,j*.5);double best=1e100;for(auto p:pts)best=std::min(best,geo::dist(z,p));assert(best<999.6);}
 std::ofstream f("results/q3_production_points.json");f<<std::setprecision(17)<<"[";for(size_t i=0;i<pts.size();++i)f<<(i?",":"")<<"["<<pts[i].x<<","<<pts[i].y<<"]";f<<"]\n";
 std::cout<<"PASS: seven shortened scan points; dense positive coverage check (analytic bound separate)\n";}
