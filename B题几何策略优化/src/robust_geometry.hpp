#pragma once
#include "geometry.hpp"
#include "bearing_types.hpp"
#include <array>
#include <queue>
namespace robust_geometry {
constexpr double eps=1.005; // ±1 degree plus the public 0.01-degree readout rounding.
struct Bound {double lower=0,upper=0;int cells=0;};
inline bool reception(const geo::Poly&p,geo::Pt q,const std::vector<dynamic_selection::Event>&h,int problem,double range=950.7){
 if(p.empty())return false;
 for(auto z:p)if(geo::dist(q,z)>range-1e-5)return false;
 if(problem==3)return true;
 // For every z, the positive observations constrain heading by homogeneous
 // halfplanes. q in the convex hull of heard sites is a sufficient dual cone
 // certificate simultaneously for all z. No heading particles certify this.
 geo::Poly heard;for(auto e:h)if(e.kind==1||e.kind==2)heard.push_back(e.q);
 return geo::contains(geo::hull(heard),q);
}
inline std::pair<double,double> angles(const geo::Poly&p,geo::Pt q){
 if(geo::contains(p,q))return {0,360};
 std::vector<double>a;for(auto z:p){double b=atan2(z.y-q.y,z.x-q.x)*180/geo::pi;if(b<0)b+=360;a.push_back(b);}
 std::sort(a.begin(),a.end());double gap=-1,start=0;
 for(size_t i=0;i<a.size();++i){double b=i+1<a.size()?a[i+1]:a[0]+360;if(b-a[i]>gap){gap=b-a[i];start=b;}}
 return {start-eps,start+360-gap+eps};
}
inline Bound worst_radius(const geo::Poly&p,geo::Pt q,int budget=96,double tolerance=.10){
 if(p.empty())return {};auto old=geo::mec(p);
 auto range=angles(p,q);
 struct Cell{double a,b,upper,lower;bool operator<(const Cell&o)const{return upper<o.upper;}};
 auto cell=[&](double a,double b){double mid=(a+b)/2;
  auto outer=geo::observe(p,q,mid,eps+(b-a)/2+1e-9);
  auto exact=geo::observe(p,q,mid,eps);
  double up=outer.empty()?0:std::min(old.r,geo::mec(outer).r+1e-6);
  double lo=exact.empty()?0:std::max(0.,geo::mec(exact).r);
  return Cell{a,b,up,lo};
 };
 std::priority_queue<Cell>todo;int initial=std::max(1,int(ceil((range.second-range.first)/12.)));double lower=0;int used=0;
 for(int i=0;i<initial;++i){auto x=cell(range.first+(range.second-range.first)*i/initial,range.first+(range.second-range.first)*(i+1)/initial);lower=std::max(lower,x.lower);todo.push(x);++used;}
 while(used+2<=budget&&!todo.empty()&&todo.top().upper>lower+tolerance){auto x=todo.top();todo.pop();double mid=(x.a+x.b)/2;for(auto y:{cell(x.a,mid),cell(mid,x.b)}){lower=std::max(lower,y.lower);todo.push(y);++used;}}
 return {lower,todo.empty()?0:std::max(lower,todo.top().upper)+1e-5,used};
}
inline geo::Pt project_reception(geo::Pt q,const geo::Poly&p,double range=950.69){
 for(int pass=0;pass<24;++pass){double maxmove=0;for(auto z:p){double d=geo::dist(q,z);if(d>range){auto n=z+(q-z)*(range/d);maxmove=std::max(maxmove,geo::dist(q,n));q=n;}}if(maxmove<1e-6)break;}return q;
}
// Deterministic simplex optimization of the geometric objective. It neither
// quantizes bearings nor performs eight-direction particle pattern search.
template<class Score> geo::Pt simplex(geo::Pt seed,double scale,Score score,int steps=26){
 struct V{geo::Pt q;double s;};auto at=[&](geo::Pt q){return V{q,score(q)};};
 std::array<V,3>x{at(seed),at(seed+geo::Pt{scale,0}),at(seed+geo::Pt{0,scale})};
 for(int it=0;it<steps;++it){std::sort(x.begin(),x.end(),[](auto a,auto b){return a.s<b.s;});auto c=(x[0].q+x[1].q)/2;auto r=at(c*2-x[2].q);
  if(r.s<x[0].s){auto e=at(c+(r.q-c)*2);x[2]=e.s<r.s?e:r;}
  else if(r.s<x[1].s)x[2]=r;
  else{auto s=at(c+(r.s<x[2].s?r.q-c:x[2].q-c)*.5);if(s.s<std::min(r.s,x[2].s))x[2]=s;else for(int j=1;j<3;++j)x[j]=at((x[0].q+x[j].q)/2);}
 }
 return std::min_element(x.begin(),x.end(),[](auto a,auto b){return a.s<b.s;})->q;
}
struct Candidate{bool valid=false;geo::Pt q;double rho=INFINITY,cost=INFINITY;};
inline Candidate candidate(const geo::Poly&p,geo::Pt now,geo::Pt first,double angle,const std::vector<dynamic_selection::Event>&history,int problem,int mode){
 Candidate best;if(p.empty()||problem==4)return best; // one positive bearing has no new universal heading guarantee.
 auto c=geo::mec(p);if(c.r<=20)return best;
 auto u=geo::polar(1,angle);geo::Pt v{-u.y,u.x};
 geo::Poly seeds{project_reception(now,p),project_reception(c.c,p)};
 for(double side:{-1.,1.})seeds.push_back(project_reception(first+u*750+v*(side*300),p));
 auto valid=[&](geo::Pt q){if(geo::norm(q)>2671.99||!reception(p,q,history,problem))return false;for(auto e:history)if(e.kind<=2&&geo::dist(e.q,q)<.5)return false;return true;};
 auto score=[&](geo::Pt q){if(!valid(q))return 1e8+geo::dist(q,project_reception(q,p))*1000;double r=worst_radius(p,q,64,.25).upper;
  return mode==2?geo::dist(now,q)+500*std::max(0.,r-34.8):r;};
 std::sort(seeds.begin(),seeds.end(),[&](auto a,auto b){return score(a)<score(b);});
 for(int i=0;i<2;++i){auto q=simplex(seeds[i],75,score,22);if(!valid(q))continue;double r=worst_radius(p,q,256,.03).upper;
  if(mode==2&&r>35)continue;double cost=mode==2?geo::dist(now,q):r;
  if(cost<best.cost)best={true,q,r,cost};}
 return best;
}
}
