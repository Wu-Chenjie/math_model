#pragma once
#include "geometry.hpp"
#include "bearing_types.hpp"
namespace neighborhood_tour {
inline bool valid(geo::Pt q,const geo::Poly&cell){for(auto z:cell)if(geo::dist(q,z)>20-1e-6)return false;return true;}
inline geo::Pt project(geo::Pt q,const geo::Poly&cell){for(int pass=0;pass<24;++pass){double shift=0;for(auto z:cell){double d=geo::dist(q,z);if(d>20-1e-5){auto next=z+(q-z)*((20-1e-5)/d);shift=std::max(shift,geo::dist(q,next));q=next;}}if(shift<1e-8)break;}return q;}
inline double length(const geo::Poly&r,geo::Pt start){double out=0;for(auto q:r){out+=geo::dist(start,q);start=q;}return out;}
inline geo::Poly optimize(geo::Poly route,const std::vector<geo::Poly>&cells,geo::Pt start){
 if(route.size()!=cells.size())throw std::runtime_error("neighborhood size mismatch");
 for(int pass=0;pass<5;++pass)for(size_t ii=0;ii<route.size();++ii){size_t i=pass%2?route.size()-1-ii:ii;if(cells[i].empty())continue;
  auto prev=i?route[i-1]:start;auto next=i+1<route.size()?route[i+1]:prev;
  auto cost=[&](geo::Pt q){return geo::dist(prev,q)+(i+1<route.size()?geo::dist(q,next):0);};
  auto best=route[i];double value=cost(best);auto trial=[&](geo::Pt q){q=project(q,cells[i]);if(valid(q,cells[i])&&cost(q)<value-1e-8){best=q;value=cost(q);}};
  auto d=next-prev;double fraction=geo::dot(d,d)>0?std::clamp(geo::dot(best-prev,d)/geo::dot(d,d),0.,1.):0;
  trial(prev+d*fraction);trial((prev+next)/2);
  for(int step=0;step<12;++step){auto a=best-prev,b=best-next;auto grad=a/std::max(1e-9,geo::norm(a));if(i+1<route.size())grad=grad+b/std::max(1e-9,geo::norm(b));trial(best-grad*(8./(1+step)));}
  route[i]=best;
 }
 return route;
}
inline double expected(const geo::Poly&r,geo::Pt start,const std::vector<dynamic_selection::Hypothesis>&h){double mass=0,out=0;for(auto s:h){double t=0;auto q=start;bool found=false;for(auto p:r){t+=geo::dist(q,p)/5;q=p;if(geo::dist(p,s.z)<=20){t+=5;found=true;break;}t+=3;}if(!found)return INFINITY;mass+=s.weight;out+=s.weight*t;}return mass>0?out/mass:INFINITY;}
inline geo::Poly optical(const geo::Poly&base,const geo::Poly&centers,const std::vector<geo::Poly>&original_cells,geo::Pt start,const std::vector<dynamic_selection::Hypothesis>&h){
 std::vector<geo::Poly>cells;std::vector<bool>used(centers.size());
 for(auto q:base){bool mapped=false;for(size_t i=0;i<centers.size();++i)if(!used[i]&&geo::dist(q,centers[i])<1e-7){used[i]=true;cells.push_back(original_cells[i]);mapped=true;break;}if(!mapped)return base;}
 auto best=base;double bestlen=length(base,start),bestexp=expected(base,start,h);
 auto consider=[&](geo::Poly candidate,const std::vector<geo::Poly>&regions){candidate=optimize(candidate,regions,start);double l=length(candidate,start),e=expected(candidate,start,h);if(l<bestlen-1e-6&&e<bestexp-1e-6){best=candidate;bestlen=l;bestexp=e;}};
 consider(base,cells);
 // Jointly reorder the neighborhoods, then resolve their visit positions.
 auto tour=base;auto regions=cells;
 for(int pass=0;pass<2;++pass){double gain=0;size_t ai=0,aj=0;for(size_t i=0;i<tour.size();++i)for(size_t j=i+1;j<tour.size();++j){auto a=i?tour[i-1]:start;double old=geo::dist(a,tour[i]),fresh=geo::dist(a,tour[j]);if(j+1<tour.size()){old+=geo::dist(tour[j],tour[j+1]);fresh+=geo::dist(tour[i],tour[j+1]);}if(old-fresh>gain){gain=old-fresh;ai=i;aj=j;}}if(gain<1e-7)break;std::reverse(tour.begin()+ai,tour.begin()+aj+1);std::reverse(regions.begin()+ai,regions.begin()+aj+1);tour=optimize(tour,regions,start);consider(tour,regions);}
 return best;
}
}
