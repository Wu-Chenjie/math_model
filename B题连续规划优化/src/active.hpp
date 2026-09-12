#pragma once
#include "geometry.hpp"
namespace active {
// Envelope over bearing intervals; only a ranking surrogate, not a certified
// time bound. Real updates continue using the original conservative polygon.
inline double posterior_radius(const geo::Poly&p,geo::Pt q){
 auto c=geo::mec(p);double reference=atan2(c.c.y-q.y,c.c.x-q.x)*180/geo::pi;
 double lo=1e99,hi=-1e99;
 for(auto v:p){double a=atan2(v.y-q.y,v.x-q.x)*180/geo::pi-reference;a=std::remainder(a,360.);lo=std::min(lo,a);hi=std::max(hi,a);}
 if(hi-lo>=179)return c.r;
 lo-=1.005;hi+=1.005;double step=(hi-lo)/24,worst=0;
 for(int j=0;j<24;++j){auto post=geo::observe(p,q,reference+lo+(j+.5)*step,1.005+step/2);if(!post.empty())worst=std::max(worst,geo::mec(post).r);}
 return std::min(c.r,worst);
}
inline geo::Pt choose(const geo::Poly&p,geo::Pt pos,geo::Pt first,double angle,double A,double B,int mode){
 auto c=geo::mec(p);auto u=geo::polar(1,angle);geo::Pt v{-u.y,u.x};
 geo::Pt q1=first+u*A+v*B,q2=first+u*A-v*B;
 geo::Pt best=geo::dist(pos,q1)<geo::dist(pos,q2)?q1:q2;
 // Longest chord is an uncertainty-axis estimate, not a stochastic covariance.
 double longest=0;geo::Pt axis=u;
 for(auto a:p)for(auto b:p){double dd=geo::dist(a,b);if(dd>longest){longest=dd;axis=(a-b)/dd;}}
 geo::Pt transverse{-axis.y,axis.x};
 geo::Poly candidates{q1,q2};
 for(double along:{-.2,0.,.2})for(double side:{-1.,1.})for(double d:{50.,100.,200.,300.})candidates.push_back(c.c+axis*(along*longest)+transverse*(side*d));
 double bestscore=1e100;double weight=mode==1?1.:3.;
 for(auto q:candidates){
  if(geo::contains(p,q)||geo::norm(q)>2671.)continue;
  double nearest=1e100,farthest=0;
  for(size_t i=0;i<p.size();++i){nearest=std::min(nearest,geo::segment_distance(q,p[i],p[(i+1)%p.size()]));farthest=std::max(farthest,geo::dist(q,p[i]));}
  if(nearest<10||farthest>999.9)continue;
  double r=posterior_radius(p,q);
  double score=geo::dist(pos,q)/5+6+geo::dist(q,c.c)/5+weight*r/5;
  if(score<bestscore){bestscore=score;best=q;}
 }return best;
}
}
