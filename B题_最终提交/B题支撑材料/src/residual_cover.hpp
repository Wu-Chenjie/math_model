#pragma once
#include "geometry.hpp"
#include <array>
namespace residual_cover {
// Outward-rounded long-double intervals certify every accepted mutation.
// Input binary64 site coordinates are represented exactly in long double.
struct I{long double lo,hi;I(long double a=0):lo(a),hi(a){}I(long double a,long double b):lo(a),hi(b){}};
inline long double down(long double x){return std::nextafter(x,-INFINITY);}
inline long double up(long double x){return std::nextafter(x,INFINITY);}
inline I operator+(I a,I b){return {down(a.lo+b.lo),up(a.hi+b.hi)};}
inline I operator-(I a,I b){return {down(a.lo-b.hi),up(a.hi-b.lo)};}
inline I operator*(I a,I b){std::array<long double,4> v{a.lo*b.lo,a.lo*b.hi,a.hi*b.lo,a.hi*b.hi};return {down(*std::min_element(v.begin(),v.end())),up(*std::max_element(v.begin(),v.end()))};}
inline I det(geo::Pt a,geo::Pt b,geo::Pt c){return (I(b.x)-I(a.x))*(I(c.y)-I(a.y))-(I(b.y)-I(a.y))*(I(c.x)-I(a.x));}
inline I distance2(geo::Pt a,geo::Pt b){I x=I(a.x)-I(b.x),y=I(a.y)-I(b.y);return x*x+y*y;}
struct Box{double x0,y0,x1,y1;int depth=0;geo::Poly corners()const{return {{x0,y0},{x1,y0},{x1,y1},{x0,y1}};}};
inline bool outside(Box b){double x=b.x0>0?b.x0:b.x1<0?b.x1:0,y=b.y0>0?b.y0:b.y1<0?b.y1:0;return distance2({x,y},{0,0}).lo>1800.L*1800.L;}
inline bool safe_box(Box b,const geo::Poly&sites){
 auto vertices=b.corners();geo::Poly safe;
 for(auto q:sites){bool in=true;for(auto z:vertices)if(distance2(q,z).hi>999.999L*999.999L){in=false;break;}if(in)safe.push_back(q);}
 auto h=geo::hull(safe);if(h.size()<3)return false;
 for(size_t i=0;i<h.size();++i){if(det(h[i],h[(i+1)%h.size()],h[(i+2)%h.size()]).lo<=0)return false;
  for(auto z:vertices)if(det(h[i],h[(i+1)%h.size()],z).lo<0)return false;}
 return true;
}
struct Certificate{bool pass=false;int checks=0;std::vector<Box>leaves;};
inline Certificate certify(const geo::Poly&sites,const std::vector<Box>&prior={},int budget=100000){
 Certificate out;std::vector<Box>todo=prior.empty()?std::vector<Box>{{-1800,-1800,1800,1800,0}}:prior;
 while(!todo.empty()){
  auto b=todo.back();todo.pop_back();if(outside(b))continue;
  if(++out.checks>budget)return out;
  if(safe_box(b,sites)){out.leaves.push_back(b);continue;}
  if(b.depth>=30)return out;
  // An uncovered center is a quick rejection, never an acceptance test.
  geo::Pt c{(b.x0+b.x1)/2,(b.y0+b.y1)/2};
  if(geo::norm(c)<1800){geo::Poly near;for(auto p:sites)if(geo::dist(c,p)<=1000)near.push_back(p);if(!geo::contains(geo::hull(near),c))return out;}
  if(b.x1-b.x0>=b.y1-b.y0){double m=(b.x0+b.x1)/2;todo.push_back({b.x0,b.y0,m,b.y1,b.depth+1});todo.push_back({m,b.y0,b.x1,b.y1,b.depth+1});}
  else{double m=(b.y0+b.y1)/2;todo.push_back({b.x0,b.y0,b.x1,m,b.depth+1});todo.push_back({b.x0,m,b.x1,b.y1,b.depth+1});}
 }
 out.pass=true;return out;
}
class State {
 public:geo::Poly past;std::vector<Box>leaves;int calls=0,accepted=0,retired=0;double saved=0;
 geo::Poly sites(const geo::Poly&points,const std::vector<bool>&visited,int omit=-1,geo::Pt replacement={},bool add=false)const{
  geo::Poly out=past;for(int i=0;i<(int)points.size();++i)if(!visited[i]&&i!=omit)out.push_back(points[i]);if(add)out.push_back(replacement);return out;
 }
 bool verify(const geo::Poly&s,bool commit){++calls;auto c=certify(s,leaves);if(c.pass&&commit)leaves=std::move(c.leaves);return c.pass;}
 void scanned(geo::Pt q){past.push_back(q);}
 void retire(geo::Poly&points,std::vector<bool>&visited){
  // With no extra/replaced site, deleting an essential static point cannot
  // become sound merely because other static points gave negative readings.
  for(int i=0;i<(int)points.size();++i)if(!visited[i]&&verify(sites(points,visited,i),true)){visited[i]=true;++retired;}
 }
 geo::Pt replace(const geo::Poly&points,const std::vector<bool>&visited,int i,geo::Pt now){
  auto old=points[i];if(geo::dist(old,now)<5)return old;
  auto valid=[&](geo::Pt q,bool commit){return verify(sites(points,visited,i,q,true),commit);};
  if(valid(now,true)){++accepted;saved+=geo::dist(old,now);return now;}
  // Closest certified point on this segment; feasibility is checked at every
  // accepted point. Bisection is a heuristic search, not a monotonicity claim.
  double low=0,high=1;geo::Pt best=old;
  for(int it=0;it<7;++it){double m=(low+high)/2;auto q=old+(now-old)*m;if(valid(q,false)){low=m;best=q;}else high=m;}
  if(geo::dist(best,old)>=2&&valid(best,true)){++accepted;saved+=geo::dist(best,old);return best;}return old;
 }
};
}
