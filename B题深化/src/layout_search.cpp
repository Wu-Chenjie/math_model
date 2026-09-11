#include "geometry.hpp"
#include "routing.hpp"
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace geo;
Poly shifted(double h,double a,double b,bool origin=true){
 Poly p;if(origin)p.push_back({0,0});auto v=[&](int i,int j){return Pt{h*(i+a+.5*(j+b)),h*sqrt(3.)/2*(j+b)};};
 for(int i=-6;i<6;++i)for(int j=-6;j<6;++j){Pt x=v(i,j),y=v(i+1,j),z=v(i,j+1),w=v(i+1,j+1);
  for(auto q:{Poly{x,y,z},Poly{w,z,y}})if(meets_disk(q,1800))for(auto s:q){bool dup=false;for(auto t:p)if(dist(s,t)<1e-6)dup=true;if(!dup)p.push_back(s);}}
 return p;
}
int main(int argc,char**argv){std::ofstream out(argc>1?argv[1]:"layout.csv");out<<"h,a,b,points,route_m\n";int best=100;double bestL=1e99,bh=0,ba=0,bb=0;Poly bestp;
 for(double h:{950.,975.,990.,999.})for(int ia=0;ia<24;++ia)for(int ib=0;ib<24;++ib){double a=ia/24.,b=ib/24.;auto p=shifted(h,a,b);if((int)p.size()>best)continue;
  auto r=route::optimize({0,0},p);double L=route::length({0,0},p,r);out<<h<<","<<a<<","<<b<<","<<p.size()<<","<<L<<"\n";
  if((int)p.size()<best||((int)p.size()==best&&L<bestL)){best=p.size();bestL=L;bh=h;ba=a;bb=b;bestp=p;}}
 std::cout<<"Best: h="<<bh<<" a="<<ba<<" b="<<bb<<" points="<<best<<" route="<<bestL<<"\n";
 std::ofstream coords(argc>2?argv[2]:"layout_points.csv");coords<<"x,y\n";for(auto p:bestp)coords<<std::setprecision(17)<<p.x<<","<<p.y<<"\n";
}
