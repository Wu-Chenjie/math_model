#pragma once
#include "geometry.hpp"
#define B_CONTINUOUS_POINTS 1
namespace continuous_points {
template<class Score,class Valid>
geo::Poly refine(const geo::Poly& seeds,Score score,Valid valid,int budget,double scale){
 std::vector<std::pair<double,geo::Pt>> evaluated;
 int calls=0;
 auto evaluate=[&](geo::Pt q){if(calls>=budget||!valid(q))return;
  for(auto x:evaluated)if(geo::dist(q,x.second)<1e-7)return;
  ++calls;double value=score(q);if(!std::isfinite(value))return;evaluated.push_back({value,q});
 };
 for(auto q:seeds)evaluate(q);if(evaluated.empty())return {};
 auto best=[&](){return std::min_element(evaluated.begin(),evaluated.end(),[](auto a,auto b){return a.first<b.first;})->second;};
 for(int level=0;level<6&&calls<budget;++level){
  for(int repeat=0;repeat<2&&calls<budget;++repeat){auto center=best();
   for(int k=0;k<8;++k)evaluate(center+geo::polar(scale,45.*k));
   if(geo::dist(center,best())<1e-7)break;
  }scale*=.5;
 }
 std::stable_sort(evaluated.begin(),evaluated.end(),[](auto a,auto b){return a.first<b.first;});
 geo::Poly out;for(auto x:evaluated){out.push_back(x.second);if(out.size()==6)break;}return out;
}
}
