#include "../src/adaptive_optical.hpp"
#include <iostream>
#include <cassert>
#include <random>
int main(){
 auto p=geo::observe(geo::outer_disk({0,0},1500),{0,0},0);p=geo::clip(p,{1,0},1500);
#ifdef B_VARIABLE_COVER
 auto route=adaptive_optical::variable_cover(p,{0,0},0);
#else
 auto route=adaptive_optical::cover(p,{0,0},0);
#endif
 if(route.size()>70){std::cerr<<"FAIL variable strip packing should use <=70 centers, got "<<route.size()<<"\n";return 1;}
#ifdef B_VARIABLE_COVER
 for(double angle:{0.,37.,147.,299.})for(double length:{1.,20.,200.,750.,1500.}){
  auto z=geo::observe(geo::outer_disk({0,0},length),{0,0},angle);z=geo::clip(z,geo::polar(1,angle),length);
  std::vector<geo::Poly> cells;auto q=adaptive_optical::variable_cover(z,{0,0},angle,&cells);
  assert(!q.empty()&&q.size()==cells.size());
  for(size_t i=0;i<q.size();++i){assert(!cells[i].empty());for(auto v:cells[i])assert(geo::dist(v,q[i])<20);}
  for(double x=0;x<=length;x+=std::max(.2,length/500))for(double t:{-.01754,-.01,0.,.01,.01754}){
   auto v=geo::polar(x,angle)+geo::polar(t*x,angle+90);if(!geo::contains(z,v))continue;
   bool hit=false;for(auto c:q)hit|=geo::dist(c,v)<=20;assert(hit);
  }
 }
 auto single=adaptive_optical::variable_cover({{400,50}},{0,0},0);assert(single.size()==1&&geo::dist(single[0],{400,50})<1e-9);
 std::mt19937 random(842);auto U=[&](){return double(random())/random.max();};
 for(int trial=0;trial<100;++trial){auto source=geo::polar(1800*sqrt(U()),360*U());auto first=source+geo::polar(100+1200*U(),360*U());double angle=atan2(source.y-first.y,source.x-first.x)*180/geo::pi+2*U()-1;
  auto region=geo::observe(geo::outer_disk({0,0},1800),first,angle);region=geo::disk_clip(region,first,1500);auto axis=geo::polar(1,angle);region=geo::clip(region,axis,geo::dot(axis,first)+1500);
  for(int k=0;k<trial%4;++k){auto q=source+geo::polar(50+800*U(),360*U());double a=atan2(source.y-q.y,source.x-q.x)*180/geo::pi+2*U()-1;region=geo::observe(region,q,a);}
  std::vector<geo::Poly> cells;auto centers=adaptive_optical::variable_cover(region,first,angle,&cells);assert(centers.size()==cells.size()&&!centers.empty());
  for(size_t i=0;i<centers.size();++i)for(auto z:cells[i])assert(geo::dist(centers[i],z)<20);
  geo::Pt mean;for(auto z:region)mean=mean+z;mean=mean/double(region.size());
  for(auto vertex:region)for(int k=0;k<=20;++k){auto z=mean*(1-k/20.)+vertex*(k/20.);bool hit=false;for(auto c:centers)hit|=geo::dist(c,z)<20;assert(hit);}
 }
#endif
 std::cout<<"PASS variable-width covering: "<<route.size()<<" centers, certified convex cells and rotated coverage\n";
}
