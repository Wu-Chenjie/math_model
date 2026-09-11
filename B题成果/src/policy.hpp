#pragma once
#include "geometry.hpp"
#include <array>
#include <stdexcept>
using geo::Pt;using geo::Poly;
struct Reading {int kind=0;double angle=0;}; // no_signal=0, near=1, direction=2
struct Sensor {virtual Reading measure(Pt,int)=0;virtual bool clear(Pt,int)=0;virtual void audit(int,const Poly&){};virtual ~Sensor()=default;};
struct Track {Poly p;Pt first;double angle=0;int obs=0;bool cleared=false;};
struct Options {double spacing=950,early=35;bool square=false,dynamic=true;};
class Policy {
 Sensor& io;int problem;Options opt;std::array<Track,21> t;
 public:Pt pos;int channel=1,cleared=0,fallbacks=0;std::string certificate="incomplete";
 Policy(Sensor& s,int prob,Options o={}):io(s),problem(prob),opt(o){}
 Reading measure(Pt p,int k){auto r=io.measure(p,k);pos=p;channel=k;
  if(r.kind==1){if(!clear(p,k))throw std::runtime_error("near followed by failed clear");}
  else if(r.kind==2){auto &a=t[k];if(a.obs==0){a.p=geo::outer_disk({0,0},1800);a.first=p;a.angle=r.angle;}
   a.p=geo::observe(a.p,p,r.angle);a.p=geo::disk_clip(a.p,p,1500);
   // Valid axial bound additionally prevents circumscribed-disk overshoot along bearing.
   Pt u=geo::polar(1,r.angle);a.p=geo::clip(a.p,u,geo::dot(u,p)+1500);
   ++a.obs;if(a.p.empty())throw std::runtime_error("empty feasible region");io.audit(k,a.p);}
  return r;
 }
 bool clear(Pt p,int k){bool ok=io.clear(p,k);pos=p;if(ok&&!t[k].cleared){t[k].cleared=true;++cleared;}return ok;}
 void optical(int k){++fallbacks;auto &a=t[k];Pt u=geo::polar(1,a.angle),v={-u.y,u.x};
  double xmin=1e99,xmax=-1e99,ymin=1e99,ymax=-1e99;
  for(auto p:a.p){Pt d=p-a.first;double x=geo::dot(d,u),y=geo::dot(d,v);xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);}
  int nx=std::max(1,(int)ceil((xmax-xmin)/28)),ny=std::max(1,(int)ceil((ymax-ymin)/28));
  Poly route;for(int i=0;i<nx;++i)for(int jj=0;jj<ny;++jj){int j=i%2?ny-1-jj:jj;route.push_back(a.first+u*(xmin+(i+.5)*(xmax-xmin)/nx)+v*(ymin+(j+.5)*(ymax-ymin)/ny));}
  if(geo::dist(pos,route.back())<geo::dist(pos,route.front()))std::reverse(route.begin(),route.end());
  for(auto p:route)if(clear(p,k))return;
  throw std::runtime_error("continuous optical coverage exhausted without success");
 }
 void locate(int k){auto &a=t[k];if(a.cleared)return;
  if(a.obs==1){Pt u=geo::polar(1,a.angle),v={-u.y,u.x};Pt q1=a.first+u*750+v*300,q2=a.first+u*750-v*300;
   if(geo::dist(pos,q2)<geo::dist(pos,q1))std::swap(q1,q2);
   auto r=measure(q1,k);if(a.cleared)return;
   if(r.kind==0){measure(q2,k);if(a.cleared)return;}
  }
  for(int attempt=0;attempt<3&&!a.cleared;++attempt){auto c=geo::mec(a.p);
   if(c.r<=opt.early || c.r<=20-1e-6){if(clear(c.c,k))return;}
   if(a.obs<2)break;
   Pt q=c.c;
   if(geo::dist(pos,q)<1){Pt u=geo::polar(1,a.angle);q=q+Pt{-u.y,u.x}*(attempt%2?-50:50);}
   auto r=measure(q,k);if(a.cleared)return;
   if(r.kind==0){Pt u=geo::polar(1,a.angle),v={-u.y,u.x};measure(c.c+v*50,k);if(a.cleared)return;}
  }
  if(!a.cleared)optical(k);
 }
 void run(){Poly points=geo::coverage(problem,opt.square?600:opt.spacing,opt.square);std::vector<bool> visited(points.size());
  for(size_t step=0;step<points.size();++step){size_t j=points.size();double best=1e99;
   for(size_t i=0;i<points.size();++i)if(!visited[i]){double score=opt.dynamic?geo::dist(pos,points[i]):double(i);if(score<best){best=score;j=i;}}
   visited[j]=true;Pt q=points[j];int start=channel;
   for(int a=0;a<20;++a){int k=1+(start-1+a)%20;if(!t[k].cleared&&t[k].obs==0)measure(q,k);}
   while(cleared<16){int kbest=0;best=1e99;for(int k=1;k<=20;++k)if(t[k].obs>0&&!t[k].cleared){double d=opt.dynamic?geo::dist(pos,geo::mec(t[k].p).c):k;if(d<best){best=d;kbest=k;}}if(!kbest)break;locate(kbest);}
   if(cleared==16){certificate="upper_bound_16";return;}
  }
  for(int k=1;k<=20;++k)if(t[k].obs&&!t[k].cleared)throw std::runtime_error("pending source at exit");
  certificate=problem==3?"seven_point_per_channel":"convex_mesh_per_channel";
 }
};
