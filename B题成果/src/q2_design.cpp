#include "geometry.hpp"
#include <fstream>
#include <iostream>
using namespace geo;
int main(int argc,char**argv){
 std::ofstream out(argc>1?argv[1]:"q2.csv");out<<"a,b,worst_radius_m,mean_radius_m,travel_m,samples\n";
 Poly first=observe(outer_disk({0,0},1500,96),{0,0},0);first=clip(first,{1,0},1500);
 for(double a:{650.,750.,850.})for(double b:{0.,200.,300.,400.}){
  Pt q={a,b};double worst=0,sum=0;int n=0;
  for(int rr=1;rr<=60;++rr)for(double ph:{-1.005,0.,1.005}){Pt z=polar(25*rr,ph);if(dist(z,q)<=5)continue;
   for(double e:{-1.005,0.,1.005}){double theta=atan2(z.y-q.y,z.x-q.x)*180/pi+e;
    auto p=observe(first,q,theta);if(p.empty())return 1;double r=mec(p).r;worst=std::max(worst,r);sum+=r;++n;}}
  out<<a<<","<<b<<","<<worst<<","<<sum/n<<","<<norm(q)<<","<<n<<"\n";
 }
 std::cout<<"Q2 deterministic scenario ranking complete\n";
}
