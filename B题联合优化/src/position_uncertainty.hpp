#pragma once
#include "geometry.hpp"
namespace position_error {
inline geo::Poly update(geo::Poly p,geo::Pt s,double angle,double eta){
 double eps=1.005*geo::pi/180,t=tan(eps);auto u=geo::polar(1,angle);geo::Pt v={-u.y,u.x};
 for(auto n:{v-u*t,v*(-1)-u*t})p=geo::clip(p,n,geo::dot(n,s)+eta*geo::norm(n));
 p=geo::disk_clip(p,s,1500+eta);p=geo::clip(p,u,geo::dot(u,s)+1500+eta);p=geo::clip(p,u*(-1),-geo::dot(u,s)+eta);
 for(auto n:{v,v*(-1)})p=geo::clip(p,n,geo::dot(n,s)+1500*sin(eps)+eta);
 return p;
}
inline double grid_side(double eta){return std::min(28.,sqrt(2.)*(20-eta)-1e-6);}
}
