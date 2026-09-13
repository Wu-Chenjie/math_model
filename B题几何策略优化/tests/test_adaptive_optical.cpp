#include "../src/adaptive_optical.hpp"
#include <cassert>
#include <iostream>
#include <random>
int main(){geo::Poly triangle{{0,0},{1500,-26},{1500,26}};auto q=adaptive_optical::cover(triangle,{0,0},0);assert(!q.empty()&&q.size()<108);
 for(int i=0;i<=150;++i)for(int j=-10;j<=10;++j){geo::Pt z{10.*i,(i/150.)*26*j/10.};double d=1e99;for(auto p:q)d=std::min(d,geo::dist(p,z));assert(d<=20);}
 geo::Pt offset{100,200};geo::Poly rotated;auto u=geo::polar(1,71.3);geo::Pt v{-u.y,u.x};for(auto z:triangle)rotated.push_back(offset+u*z.x+v*z.y);auto r=adaptive_optical::cover(rotated,offset,71.3);assert(r.size()==q.size());for(size_t i=0;i<q.size();++i)assert(geo::dist(r[i],offset+u*q[i].x+v*q[i].y)<1e-6);
 auto point=adaptive_optical::cover({{42,10}},{0,0},0);assert(point.size()==1&&geo::dist(point[0],{42,10})<1e-6);
 std::mt19937 rng(913);auto U=[&](){return double(rng())/rng.max();};
 for(int trial=0;trial<100;++trial){auto source=geo::polar(1800*sqrt(U()),360*U());auto first=source+geo::polar(300+900*U(),360*U());double direction=atan2(source.y-first.y,source.x-first.x)*180/geo::pi+2*U()-1;
  auto polygon=geo::observe(geo::outer_disk({0,0},1800),first,direction);polygon=geo::disk_clip(polygon,first,1500);auto axis=geo::polar(1,direction);polygon=geo::clip(polygon,axis,geo::dot(axis,first)+1500);
  for(int k=0;k<trial%4;++k){auto station=source+geo::polar(100+900*U(),360*U());double bearing=atan2(source.y-station.y,source.x-station.x)*180/geo::pi+2*U()-1;polygon=geo::observe(polygon,station,bearing);}
  assert(geo::contains(polygon,source));auto centers=adaptive_optical::cover(polygon,first,direction);assert(!centers.empty()&&centers.size()<=108);
  geo::Pt mean;for(auto z:polygon)mean=mean+z;mean=mean/double(polygon.size());
  for(auto vertex:polygon)for(int k=0;k<=20;++k){auto z=mean*(1-k/20.)+vertex*(k/20.);double best=1e99;for(auto c:centers)best=std::min(best,geo::dist(z,c));assert(best<20);}
 }
 std::cout<<"PASS adaptive optical: "<<q.size()<<" instead of108 centers; triangle coverage, rotation and singleton\n";
}
