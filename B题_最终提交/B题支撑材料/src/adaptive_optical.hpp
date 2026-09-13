#pragma once
#include "geometry.hpp"
#include <stdexcept>
namespace adaptive_optical {
#define B_VARIABLE_COVER 1
inline geo::Poly variable_cover(const geo::Poly&p,geo::Pt first,double angle,std::vector<geo::Poly>*certificate=nullptr){
 if(certificate)certificate->clear();if(p.empty())return {};
 auto whole=geo::mec(p);if(whole.r<20-1e-4){if(certificate)certificate->push_back(p);return {whole.c};}
 auto u=geo::polar(1,angle);geo::Pt v{-u.y,u.x};geo::Poly local;
 double xmin=INFINITY,xmax=-INFINITY,ymin=INFINITY,ymax=-INFINITY;
 for(auto z:p){auto d=z-first;local.push_back({geo::dot(d,u),geo::dot(d,v)});xmin=std::min(xmin,local.back().x);xmax=std::max(xmax,local.back().x);ymin=std::min(ymin,local.back().y);ymax=std::max(ymax,local.back().y);}
 struct Packing {bool valid=true;geo::Poly centers;std::vector<geo::Poly>cells;};
 auto pack=[&](double left,double right,int rows){Packing result;
  auto strip=geo::clip(geo::clip(local,{-1,0},-left+1e-6),{1,0},right+1e-6);
  if(strip.empty()){result.valid=false;return result;}
  double bottom=INFINITY,top=-INFINITY;for(auto z:strip){bottom=std::min(bottom,z.y);top=std::max(top,z.y);}
  for(int j=0;j<rows;++j){double a=bottom+(top-bottom)*j/rows,b=bottom+(top-bottom)*(j+1)/rows;
   auto cell=geo::clip(geo::clip(strip,{0,-1},-a+1e-6),{0,1},b+1e-6);if(cell.empty())continue;
   auto circle=geo::mec(cell);if(!(circle.r<20-1e-4)){result.valid=false;return result;}
   result.centers.push_back(circle.c);result.cells.push_back(std::move(cell));
  }return result;
 };
 geo::Poly out;double left=xmin;int strips=0;
 do{
  double remaining=xmax-left,chosen_width=-1,efficiency=-1;Packing chosen;
  std::vector<int> row_counts{1,2};int fallback_rows=std::max(1,int(ceil((ymax-ymin)/28)));
  if(fallback_rows>2)row_counts.push_back(fallback_rows);
  for(int rows:row_counts){double low=0,high=std::min(39.99,std::max(0.,remaining));
   auto start=pack(left,left,rows);if(!start.valid)continue;
   auto full=pack(left,left+high,rows);
   if(full.valid)low=high;else for(int iteration=0;iteration<14;++iteration){double mid=(low+high)/2;if(pack(left,left+mid,rows).valid)low=mid;else high=mid;}
   auto candidate=pack(left,left+low,rows);if(!candidate.valid||candidate.centers.empty())continue;
   double score=(remaining<=1e-7?1.:low)/candidate.centers.size();
   if(score>efficiency){efficiency=score;chosen_width=low;chosen=std::move(candidate);}
  }
  if(chosen_width<0||(remaining>1e-7&&chosen_width<1e-7))throw std::runtime_error("variable cover made no progress");
  if(strips%2){std::reverse(chosen.centers.begin(),chosen.centers.end());std::reverse(chosen.cells.begin(),chosen.cells.end());}
  for(size_t i=0;i<chosen.centers.size();++i){auto c=chosen.centers[i];out.push_back(first+u*c.x+v*c.y);
   if(certificate){geo::Poly cell;for(auto z:chosen.cells[i])cell.push_back(first+u*z.x+v*z.y);certificate->push_back(std::move(cell));}
  }
  left+=chosen_width;if(++strips>10000)throw std::runtime_error("variable cover exceeds strip budget");
 }while(left<xmax-1e-7);
 return out;
}
inline geo::Poly cover(const geo::Poly&p,geo::Pt first,double angle,std::vector<geo::Poly>*certificate=nullptr){
 if(certificate)certificate->clear();
 if(p.empty())return {};auto u=geo::polar(1,angle);geo::Pt v{-u.y,u.x};geo::Poly local;
 double xmin=1e99,xmax=-1e99;for(auto z:p){auto d=z-first;local.push_back({geo::dot(d,u),geo::dot(d,v)});xmin=std::min(xmin,local.back().x);xmax=std::max(xmax,local.back().x);}
 int nx=std::max(1,int(ceil((xmax-xmin)/28)));geo::Poly out;
 for(int i=0;i<nx;++i){double left=xmin+i*(xmax-xmin)/nx,right=xmin+(i+1)*(xmax-xmin)/nx;auto cell=geo::clip(geo::clip(local,{-1,0},-left+1e-5),{1,0},right+1e-5);if(cell.empty())continue;
  auto c=geo::mec(cell);if(c.r<20-1e-5){out.push_back(first+u*c.c.x+v*c.c.y);if(certificate){geo::Poly global;for(auto z:cell)global.push_back(first+u*z.x+v*z.y);certificate->push_back(global);}continue;}
  double bottom=1e99,top=-1e99;for(auto z:cell){bottom=std::min(bottom,z.y);top=std::max(top,z.y);}int ny=std::max(1,int(ceil((top-bottom)/28)));
  for(int jj=0;jj<ny;++jj){int j=i%2?ny-1-jj:jj;double a=bottom+j*(top-bottom)/ny,b=bottom+(j+1)*(top-bottom)/ny;
   auto part=geo::clip(geo::clip(cell,{0,-1},-a+1e-5),{0,1},b+1e-5);if(part.empty())continue;auto circle=geo::mec(part);
   if(circle.r>=20-1e-5)throw std::runtime_error("adaptive optical subcell radius exceeds20");out.push_back(first+u*circle.c.x+v*circle.c.y);if(certificate){geo::Poly global;for(auto z:part)global.push_back(first+u*z.x+v*z.y);certificate->push_back(global);}
  }
 }return out;
}
}
