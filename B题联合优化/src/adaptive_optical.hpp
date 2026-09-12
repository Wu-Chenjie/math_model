#pragma once
#include "geometry.hpp"
#include <stdexcept>
namespace adaptive_optical {
inline geo::Poly cover(const geo::Poly&p,geo::Pt first,double angle){
 if(p.empty())return {};auto u=geo::polar(1,angle);geo::Pt v{-u.y,u.x};geo::Poly local;
 double xmin=1e99,xmax=-1e99;for(auto z:p){auto d=z-first;local.push_back({geo::dot(d,u),geo::dot(d,v)});xmin=std::min(xmin,local.back().x);xmax=std::max(xmax,local.back().x);}
 int nx=std::max(1,int(ceil((xmax-xmin)/28)));geo::Poly out;
 for(int i=0;i<nx;++i){double left=xmin+i*(xmax-xmin)/nx,right=xmin+(i+1)*(xmax-xmin)/nx;auto cell=geo::clip(geo::clip(local,{-1,0},-left+1e-5),{1,0},right+1e-5);if(cell.empty())continue;
  auto c=geo::mec(cell);if(c.r<20-1e-5){out.push_back(first+u*c.c.x+v*c.c.y);continue;}
  double bottom=1e99,top=-1e99;for(auto z:cell){bottom=std::min(bottom,z.y);top=std::max(top,z.y);}int ny=std::max(1,int(ceil((top-bottom)/28)));
  for(int jj=0;jj<ny;++jj){int j=i%2?ny-1-jj:jj;double a=bottom+j*(top-bottom)/ny,b=bottom+(j+1)*(top-bottom)/ny;
   auto part=geo::clip(geo::clip(cell,{0,-1},-a+1e-5),{0,1},b+1e-5);if(part.empty())continue;auto circle=geo::mec(part);
   if(circle.r>=20-1e-5)throw std::runtime_error("adaptive optical subcell radius exceeds20");out.push_back(first+u*circle.c.x+v*circle.c.y);
  }
 }return out;
}
}
