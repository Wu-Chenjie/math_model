#include "../src/policy.hpp"
#include <iostream>
int main(){auto p=geo::observe(geo::outer_disk({0,0},1800),{0,0},0);p=geo::disk_clip(p,{0,0},1500);p=geo::clip(p,{1,0},1500);std::vector<dynamic_selection::Event>h{{{0,0},2,0}};
 for(int mode:{1,2}){auto q=robust_geometry::candidate(p,{0,0},{0,0},0,h,3,mode);std::cout<<mode<<" valid "<<q.valid<<" q "<<q.q.x<<","<<q.q.y<<" rho "<<q.rho<<"\n";}
 for(auto q:geo::Poly{{750,300},{750,0},{680,150},{700,150},{650,250}}){auto b=robust_geometry::worst_radius(p,q,512);std::cout<<q.x<<","<<q.y<<" "<<b.lower<<" "<<b.upper<<"\n";}}
