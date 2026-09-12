#pragma once
#include "geometry.hpp"
#include "belief_dp.hpp"
#include <numeric>
namespace dynamic_selection {
struct Event {geo::Pt q;int kind;double angle=0;};
struct Hypothesis {geo::Pt z;double radius;bool directional;double heading;double weight;};
struct Choice {bool available=false,measure=true,budget_hit=false,exact=false;geo::Pt point;double value=0;int depth=0,hypotheses=0,expanded=0;};
inline bool receives(const Hypothesis&h,geo::Pt q){return geo::dist(h.z,q)<=h.radius+1e-9&&(!h.directional||geo::dot(q-h.z,geo::polar(1,h.heading))>=-1e-9);}
inline bool consistent(const Hypothesis&h,const std::vector<Event>&events){
 for(auto e:events){double distance=geo::dist(h.z,e.q);
  if(e.kind==3){if(distance<=20)return false;continue;}
  if(e.kind==4){if(distance>20)return false;continue;}
  bool heard=receives(h,e.q);
  if(e.kind==0){if(heard)return false;}
  else if(e.kind==1){if(!heard||distance>5)return false;}
  else if(e.kind==2){double angle=atan2(h.z.y-e.q.y,h.z.x-e.q.x)*180/geo::pi;if(!heard||distance<=5||std::abs(std::remainder(angle-e.angle,360.))>1.0050001)return false;}
 }return true;
}
inline double radical(int i,int base){double a=0,b=1.;while(i){b/=base;a+=b*(i%base);i/=base;}return a;}
inline std::vector<Hypothesis> make_hypotheses(const geo::Poly&p,const std::vector<Event>&history,int problem,int cap){
 if(p.empty()||cap<1||cap>63)return {};
 geo::Pt center;for(auto q:p)center=center+q;center=center/double(p.size());
 std::vector<double>areas;double area=0;
 for(size_t i=0;i<p.size();++i){area+=std::abs(geo::cross(p[i]-center,p[(i+1)%p.size()]-center));areas.push_back(area);}
 geo::Poly positions{center};
 for(int i=1;i<=31;++i){
  if(area<1e-10){positions.push_back(p.front()*(1-i/32.)+p.back()*(i/32.));continue;}
  size_t tri=std::lower_bound(areas.begin(),areas.end(),radical(i,2)*area)-areas.begin();double a=sqrt(radical(i,3)),b=radical(i,5);
  positions.push_back(center*(1-a)+p[tri]*(a*(1-b))+p[(tri+1)%p.size()]*(a*b));
 }
 std::vector<Hypothesis>all;
 for(auto z:positions){
  double low=1000;for(auto e:history)if(e.kind==1||e.kind==2)low=std::max(low,geo::dist(z,e.q));if(low>1500+1e-7)continue;low=std::min(low,1500.);
  std::vector<double>headings;for(int i=0;i<12;++i)headings.push_back(i*30.);
  // Event boundary midpoints sample even very narrow feasible heading arcs.
  std::vector<double>cuts{0};for(auto e:history)if(e.kind<=2){double a=atan2(e.q.y-z.y,e.q.x-z.x)*180/geo::pi;for(double d:{-90.,90.})cuts.push_back(fmod(a+d+720.,360.));}
  std::sort(cuts.begin(),cuts.end());for(size_t i=0;i<cuts.size();++i){double b=i+1<cuts.size()?cuts[i+1]:cuts[0]+360.;headings.push_back(fmod((cuts[i]+b)/2,360.));}
  for(double r:{low,(low+1500)/2,1500.}){
   Hypothesis h{z,r,false,0,problem==3?1.:.5};if(consistent(h,history))all.push_back(h);
   if(problem==4)for(double a:headings){h={z,r,true,a,.5/headings.size()};if(consistent(h,history))all.push_back(h);}
  }
 }
 if(all.size()<=size_t(cap))return all;
 double total=0;for(auto h:all)total+=h.weight;
 std::vector<Hypothesis>selected;double cumulative=all[0].weight;size_t j=0;
 for(int i=0;i<cap;++i){double target=total*(i+.5)/cap;while(j+1<all.size()&&cumulative<target)cumulative+=all[++j].weight;auto h=all[j];h.weight=1.;selected.push_back(h);}
 return selected;
}
inline Choice plan(const geo::Poly&p,geo::Pt now,geo::Pt first,double angle,const std::vector<Event>&history,int problem,int depth,bool tuned,int limit){
 Choice choice;choice.depth=depth;
 auto hypotheses=make_hypotheses(p,history,problem,32);choice.hypotheses=hypotheses.size();if(hypotheses.empty())return choice;
 geo::Pt center=geo::mec(p).c,axis=geo::polar(1,angle);double longest=0;
 for(auto a:p)for(auto b:p){double d=geo::dist(a,b);if(d>longest){longest=d;axis=(b-a)/d;}}
 geo::Pt transverse{-axis.y,axis.x},u=geo::polar(1,angle),v{-u.y,u.x};
 std::vector<geo::Pt>locations;std::vector<bool>measure;
 auto add=[&](geo::Pt q,bool sensing){
  if(!std::isfinite(q.x)||!std::isfinite(q.y)||geo::norm(q)>2671.99)return;
  for(auto e:history)if((sensing?e.kind<=2:e.kind>=3)&&geo::dist(e.q,q)<1e-6)return;
  for(size_t i=0;i<locations.size();++i)if(measure[i]==sensing&&geo::dist(locations[i],q)<1e-6)return;
  locations.push_back(q);measure.push_back(sensing);
 };
 add(now,true);add(center,true);
 for(double side:{-1.,1.}){add(first+u*750+v*(side*300),true);for(double d:{50.,150.,300.})add(center+transverse*(side*d),true);}
 for(double along:{-.25,.25})for(double side:{-1.,1.})add(center+axis*(along*longest)+transverse*(side*80),true);
 add(center,false);for(double along:{-.4,-.2,.2,.4})add(center+axis*(along*longest),false);
 if(locations.empty())return choice;
 belief_dp::Model model;for(auto h:hypotheses)model.weights.push_back(h.weight);
 int n=locations.size();model.travel.assign(n+1,std::vector<double>(n+1));geo::Poly at=locations;at.push_back(now);
 for(int i=0;i<=n;++i)for(int j=0;j<=n;++j)model.travel[i][j]=geo::dist(at[i],at[j])/5;
 for(int j=0;j<n;++j){belief_dp::Action a;a.measure=measure[j];
  for(auto h:hypotheses){double distance=geo::dist(h.z,locations[j]);int out;double seconds;
   if(!a.measure){bool hit=distance<=20;out=hit?-1:0;seconds=hit?5:3;}
   else if(!receives(h,locations[j])){out=0;seconds=5;}
   else if(distance<=5){out=-1;seconds=10;}
   else{double theta=atan2(h.z.y-locations[j].y,h.z.x-locations[j].x)*180/geo::pi;out=10+int(floor(fmod(theta+720.,360.)/2.));seconds=5;}
   a.outcome.push_back(out);a.seconds.push_back(seconds);
  }model.actions.push_back(a);
 }
 model.terminal=[&](uint64_t mask,int from){
  double xmin=1e99,xmax=-1e99,ymin=1e99,ymax=-1e99,total=0;
  for(int i=0;i<(int)hypotheses.size();++i)if(mask>>i&1){auto d=hypotheses[i].z-first;double x=geo::dot(d,u),y=geo::dot(d,v);xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);total+=hypotheses[i].weight;}
  int nx=std::max(1,int(ceil((xmax-xmin)/28))),ny=std::max(1,int(ceil((ymax-ymin)/28)));geo::Poly sweep;
  for(int i=0;i<nx;++i)for(int jj=0;jj<ny;++jj){int j=i%2?ny-1-jj:jj;sweep.push_back(first+u*(xmin+(i+.5)*(xmax-xmin)/nx)+v*(ymin+(j+.5)*(ymax-ymin)/ny));}
  double best=1e100;
  for(int reverse=0;reverse<2;++reverse){if(reverse)std::reverse(sweep.begin(),sweep.end());double cumulative=0,expected=0;uint64_t remaining=mask;auto position=at[from];
   for(auto q:sweep){cumulative+=geo::dist(position,q)/5;position=q;for(int i=0;i<(int)hypotheses.size();++i)if((remaining>>i&1)&&geo::dist(q,hypotheses[i].z)<=20+1e-7){expected+=hypotheses[i].weight/total*(cumulative+5);remaining&=~(uint64_t(1)<<i);}if(!remaining)break;cumulative+=3;}
   if(remaining)throw std::runtime_error("finite terminal sweep failed");best=std::min(best,expected);
  }return best;
 };
 auto result=belief_dp::solve(model,depth,tuned,limit);choice.value=result.value;choice.expanded=result.expanded;choice.budget_hit=result.budget_hit;choice.exact=result.exact;
 if(result.action>=0){choice.available=true;choice.measure=measure[result.action];choice.point=locations[result.action];}
 return choice;
}
}
