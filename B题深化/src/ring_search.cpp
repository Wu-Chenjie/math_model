#include "geometry.hpp"
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace geo;
Poly ring(int ni,int no,double ri,double ro,double phase,bool center=true){Poly p;if(center)p.push_back({0,0});for(int i=0;i<ni;++i)p.push_back(polar(ri,phase+360.*i/ni));for(int i=0;i<no;++i)p.push_back(polar(ro,360.*i/no));return p;}
// Numeric search diagnostic only: an exact/continuous verifier must follow.
bool covered(Pt z,const Poly&p,double radius){double angles[40];int n=0;for(auto s:p){Pt d=s-z;double rr=dot(d,d);if(rr<1e-18)return true;if(rr<=radius*radius)angles[n++]=atan2(d.y,d.x);}
 if(n<3)return false;std::sort(angles,angles+n);double gap=angles[0]+2*pi-angles[n-1];for(int i=1;i<n;++i)gap=std::max(gap,angles[i]-angles[i-1]);return gap<=pi+1e-10;}
bool allcovered(const Poly&p,double radius,int nr,int nt){for(int i=nr;i>=0;--i)for(int j=0;j<nt;++j)if(!covered(polar(1800.*i/nr,360.*j/nt),p,radius))return false;return true;}
int main(int argc,char**argv){std::ofstream out(argc>1?argv[1]:"rings.csv");out<<"n,inner,outer,ri,ro,phase,radius\n";double best=2000;int bn=99;Poly bp;int matches=0;
 for(int total=20;total<=23;++total)for(int no=9;no<=14;++no){int ni=total-no-1;if(ni<5||ni>12)continue;
  for(double ri=750;ri<=1000;ri+=25)for(double ro=1825;ro<=2050;ro+=25)for(int ph=0;ph<=6;++ph){int lcm=ni*no/std::__gcd(ni,no);double phase=180.*ph/(6*lcm);Poly p=ring(ni,no,ri,ro,phase);
   if(!allcovered(p,1000,18,120))continue;
   double lo=850,hi=1100;for(int j=0;j<12;++j){double mid=(lo+hi)/2;if(allcovered(p,mid,60,720))hi=mid;else lo=mid;}
   out<<std::setprecision(12)<<total<<","<<ni<<","<<no<<","<<ri<<","<<ro<<","<<phase<<","<<hi<<"\n";++matches;
   if(hi<999.5&&(total<bn||(total==bn&&hi<best))){bn=total;best=hi;bp=p;std::cout<<"candidate n="<<total<<" inner="<<ni<<" outer="<<no<<" ri="<<ri<<" ro="<<ro<<" phase="<<phase<<" diagnostic_radius="<<hi<<std::endl;}
  }
 }
 std::ofstream points(argc>2?argv[2]:"ring_points.csv");points<<"x,y\n";for(auto p:bp)points<<std::setprecision(17)<<p.x<<","<<p.y<<"\n";std::cout<<"survivors="<<matches<<" best_n="<<bn<<" radius="<<best<<"\n";
}
