#pragma once
#include "policy.hpp"
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <random>
struct Jammer {int ch;Pt p;double radius;bool directional;double heading;bool removed=false;};
inline uint64_t mix(uint64_t z){z+=0x9e3779b97f4a7c15ULL;z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;z=(z^(z>>27))*0x94d049bb133111ebULL;return z^(z>>31);}
inline std::vector<Jammer> make_case(int problem,int seed,int stress=0){
 std::mt19937_64 rng(seed);auto U=[&](){return std::generate_canonical<double,53>(rng);};
 int n=10+rng()%7;std::vector<int>ch;for(int k=1;k<=20;++k)ch.push_back(k);std::shuffle(ch.begin(),ch.end(),rng);
 int nd=1+rng()%(n-1);std::vector<Jammer> j;
 for(int k=0;k<n;++k){Pt p;do{p=geo::polar(1800*sqrt(U()),360*U());}while(std::any_of(j.begin(),j.end(),[&](Jammer a){return geo::dist(a.p,p)<40;}));
  double r=1000+500*U(),heading=360*U();bool dir=problem==4&&k<nd;
  if(stress==1){r=1000;p=geo::polar(1800,(k+.137)*360/n);heading=atan2(p.y,p.x)*180/geo::pi;dir=problem==4&&k<n-1;}
  if(stress==2){r=1000;p={-1700.+3400.*k/(n-1),double(k%2)*.01};heading=k%2?90:270;dir=problem==4&&k<n-1;}
  if(stress==3){r=1000;p={double(k%5)*5,0};heading=k%2?0:180;dir=problem==4&&k<n-1;}
  j.push_back({ch[k],p,r,dir,heading});}return j;
}
class Sim:public Sensor {
 std::vector<Jammer> truth;int seed,errmode;std::ofstream trace;
 public:Pt pos;int channel=1,measures=0,miss=0,success=0,switches=0,audits=0;double time=0,length=0,max_violation=0;
 Sim(std::vector<Jammer> j,int s,int e,const std::string&file=""):truth(j),seed(s),errmode(e){if(!file.empty()){trace.open(file);trace<<"kind,channel,x,y,result,angle,time\n";}}
 void move(Pt q){double d=geo::dist(q,pos);length+=d;time=round((time+d/5)*1e6)/1e6;pos=q;}
 Jammer* pending(int k){for(auto &j:truth)if(j.ch==k&&!j.removed)return &j;return nullptr;}
 void check(){if(time>=360000)throw std::runtime_error("virtual deadline");}
 Reading measure(Pt p,int k)override {check();move(p);++measures;if(k!=channel){++switches;time+=1;}channel=k;time+=5;Reading r;
  auto j=pending(k);if(j&&geo::dist(p,j->p)<=j->radius&&(!j->directional||geo::dot(p-j->p,geo::polar(1,j->heading))>=-1e-9)){
   if(geo::dist(p,j->p)<=5)r.kind=1;else{r.kind=2;double a=atan2(j->p.y-p.y,j->p.x-p.x)*180/geo::pi;
    uint64_t v=mix((uint64_t)llround(p.x*100))^mix((uint64_t)llround(p.y*100)+1234567)^mix(seed);
    double e=2*(mix(v)>>11)*0x1.0p-53-1;
    if(errmode==1)e=1;if(errmode==2)e=-1;if(errmode==3)e=sin(p.x/350)*cos(p.y/350);if(errmode==4)e=(p.x>=0?1:-1);
    r.angle=fmod(round(fmod(a+e+720,360)*100)/100,360);}}
  if(trace)trace<<std::setprecision(12)<<"measure,"<<k<<","<<p.x<<","<<p.y<<","<<r.kind<<","<<r.angle<<","<<time<<"\n";return r;
 }
 bool clear(Pt p,int k)override{check();move(p);auto j=pending(k);bool ok=j&&geo::dist(p,j->p)<=20;time+=ok?5:3;if(ok){j->removed=true;++success;}else ++miss;
  if(trace)trace<<std::setprecision(12)<<"clear,"<<k<<","<<p.x<<","<<p.y<<","<<ok<<",0,"<<time<<"\n";return ok;}
 void audit(int k,const Poly&p)override{++audits;auto j=pending(k);if(j&&!geo::contains(p,j->p))throw std::runtime_error("truth excluded from conservative polygon");}
 int total()const{return(int)truth.size();}
};
