#include "../src/geometry.hpp"
#include <random>
#include <iostream>
#include <iomanip>
#include <cassert>
using namespace geo;
// Independent exhaustive supports; long double arithmetic, no production circle constructors.
double brute(const Poly&p){
 long double best=1e100L;
 auto test=[&](long double x,long double y){long double r=0;for(auto z:p)r=std::max(r,hypotl(x-z.x,y-z.y));best=std::min(best,r);};
 for(auto a:p)test(a.x,a.y);
 for(size_t i=0;i<p.size();i++)for(size_t j=0;j<i;j++)test((p[i].x+p[j].x)/2.L,(p[i].y+p[j].y)/2.L);
 for(size_t i=0;i<p.size();i++)for(size_t j=0;j<i;j++)for(size_t k=0;k<j;k++){
  long double x1=p[i].x,y1=p[i].y,x2=p[j].x,y2=p[j].y,x3=p[k].x,y3=p[k].y;
  long double d=2*(x1*(y2-y3)+x2*(y3-y1)+x3*(y1-y2));if(fabsl(d)<1e-15L)continue;
  long double a=x1*x1+y1*y1,b=x2*x2+y2*y2,c=x3*x3+y3*y3;
  test((a*(y2-y3)+b*(y3-y1)+c*(y1-y2))/d,(a*(x3-x2)+b*(x1-x3)+c*(x2-x1))/d);
 }
 return (double)best;
}
int main(){std::mt19937_64 gen(731);std::uniform_real_distribution<double> u(-1800,1800);double max_error=0;int mismatches=0;
 for(int k=0;k<100000;k++){Poly p;int n=1+gen()%10;for(int i=0;i<n;i++)p.push_back({u(gen),u(gen)});if(k%7==0)for(auto&z:p)z.y=0;if(k%11==0&&n>1)p[1]=p[0];auto a=mec(p);double b=brute(p),e=a.r-b;max_error=std::max(max_error,e);if(e>1e-6){if(mismatches++==0){std::cout<<"FIRST_MEC_FAILURE "<<std::setprecision(16)<<a.r<<" "<<b<<"\n";for(auto z:p)std::cout<<z.x<<" "<<z.y<<"\n";}}}
 std::cout<<"MEC cases=100000 mismatches="<<mismatches<<" max_absolute_excess="<<std::setprecision(15)<<max_error<<"\n";
 assert(mismatches==0);
 assert(halfplanes({}).kind=="unbounded");
 assert(halfplanes({{{0,0},-1}}).kind=="empty");
 assert(halfplanes({{{1,0},1},{{-1,0},-1}}).kind=="unbounded");
 auto point=halfplanes({{{1,0},1},{{-1,0},-1},{{0,1},2},{{0,-1},-2}});assert(point.kind=="bounded"&&point.p.size()==1);
 auto line=halfplanes({{{1,0},1},{{-1,0},-1},{{0,1},2},{{0,-1},0}});assert(line.kind=="bounded"&&line.p.size()==2);
 int excludes=0;for(int k=0;k<100000;k++) {Pt z=polar(1800.0*(gen()%10001)/10000,gen()%36000/100.);Pt s=z-polar(5.001+1494.999*(gen()%10001)/10000,gen()%36000/100.);double truea=atan2(z.y-s.y,z.x-s.x)*180/pi;double err=(k%2?1.005:-1.005);auto p=disk_clip(observe(outer_disk({0,0},1800),s,truea+err),s,1500);Pt axis=polar(1,truea+err);p=clip(p,axis,dot(axis,s)+1500);if(!contains(p,z))excludes++;}
 std::cout<<"Conservative-set boundary cases=100000 excludes="<<excludes<<"\n";assert(excludes==0);
 double e=1.005*pi/180,w=1500,h=3000*tan(e);int nx=ceil(w/28),ny=ceil(h/28);std::cout<<"Optical width="<<w<<" height="<<h<<" nx="<<nx<<" ny="<<ny<<" calls="<<nx*ny<<" max_cover_radius="<<hypot(w/nx,h/ny)/2<<"\n";
 std::cout<<"Coverage points P3="<<coverage(3).size()<<" P4="<<coverage(4).size()<<"\n";
 int hp_bad=0;
 for(int k=0;k<10000;k++) {Pt z={u(gen),u(gen)};std::vector<HP> h={{{1,0},z.x+20},{{-1,0},-z.x+20},{{0,1},z.y+20},{{0,-1},-z.y+20}};
  for(int j=0;j<10;j++){Pt a=polar(1,gen()%36000/100.);h.push_back({a,dot(a,z)+1+gen()%100});}
  auto r=halfplanes(h);if(r.kind!="bounded"||!contains(r.p,z))hp_bad++;
 }
 std::cout<<"Known-feasible bounded halfplane cases=10000 failures="<<hp_bad<<"\n";assert(hp_bad==0);
}
