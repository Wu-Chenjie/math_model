#include "../../src/policy.hpp"
#include <cassert>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>

// This sensor is independent of simulator.hpp and exposes only legal observations.
struct ReviewSensor : Sensor {
  Pt truth; bool present=false,done=false; double heading=0,error=0;
  int measures=0,clears=0,after_discovery=0; bool discovered=false;
  std::vector<std::pair<Pt,int>> measurements;
  Reading measure(Pt p,int k) override {
    ++measures;measurements.push_back({p,k});
    if(k==7&&discovered)++after_discovery;
    if(k!=7||!present||done||geo::dist(p,truth)>1000||geo::dot(p-truth,geo::polar(1,heading))<0)return {};
    discovered=true;
    if(geo::dist(p,truth)<=5)return {1,0};
    double a=atan2(truth.y-p.y,truth.x-p.x)*180/geo::pi;
    return {2,round((a+error)*100)/100};
  }
  bool clear(Pt p,int k) override {++clears;if(k==7&&present&&!done&&geo::dist(p,truth)<=20){done=true;return true;}return false;}
  void audit(int k,const Poly&p)override{assert(k==7);assert(geo::contains(p,truth));}
};
int main(int argc,char**argv){
  std::mt19937_64 rng(837451);
  auto rnd=[&](){return (double)(rng()%100000)/100.-500;};
  for(int test=0;test<300;++test){
    Poly p;for(int i=0;i<test%24;++i)p.push_back({rnd(),rnd()});
    Pt start={rnd(),rnd()};auto r=route::nearest(start,p);double before=route::length(start,p,r);
    route::two_opt(start,p,r);assert(route::length(start,p,r)<=before+1e-8);
    auto opt=route::optimize(start,p);assert(route::length(start,p,opt)<=route::length(start,p,r)+1e-8);
    std::sort(opt.begin(),opt.end());assert(opt.size()==p.size());for(int i=0;i<(int)opt.size();++i)assert(opt[i]==i);
  }
  Options o;o.spacing=999;o.shifted=true;o.shiftA=1./6;o.shiftB=11./12;o.includeOrigin=false;o.routing=2;o.opportunistic=true;
  ReviewSensor none;Policy empty(none,4,o);auto points=empty.covering_points();assert(points.size()==25);
  if(argc>1){std::ofstream f(argv[1]);f<<std::setprecision(17);for(Pt p:points)f<<p.x<<","<<p.y<<"\n";}
  empty.run();assert(none.measures==500);assert(none.clears==0);assert(empty.certificate=="convex_mesh_per_channel");
  for(Pt p:points)for(int k=1;k<=20;++k){int count=0;for(auto m:none.measurements)if(m.second==k&&geo::dist(p,m.first)<1e-8)++count;assert(count==1);}
  int trials=0,maxlocal=0,maxclear=0;
  for(Pt z:Poly{{0,0},{1800,0},{-1800,0},{0,1800},{0,-1800},{1799.999,.001},{-900,900}})
    for(int heading=0;heading<360;heading+=30)for(double e:{-1.,1.}){
      ReviewSensor s;s.present=true;s.truth=z;s.heading=heading;s.error=e;
      Policy bot(s,4,o);bot.run();assert(s.done&&bot.cleared==1);assert(s.after_discovery<=9);assert(s.clears<=111);
      maxlocal=std::max(maxlocal,s.after_discovery);maxclear=std::max(maxclear,s.clears);++trials;
    }
  std::cout<<"PASS 300 open-route contract cases; 500 absence-certificate scans; "<<trials<<" independent directional boundary cases; observed max local measures="<<maxlocal<<", clears="<<maxclear<<"\n";
}
