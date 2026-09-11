#define main coarse_main
#include "ring_search.cpp"
#undef main
int main(int argc,char**argv){std::ofstream out(argc>1?argv[1]:"refine.csv");out<<"n,ni,no,ri,ro,phase,score\n";double best=1e9;Poly bp;
 for(auto counts:{std::pair<int,int>{8,12},std::pair<int,int>{7,13},std::pair<int,int>{8,13},std::pair<int,int>{9,12}}){int ni=counts.first,no=counts.second,lcm=ni*no/std::__gcd(ni,no);
  for(double ri=982;ri<=999;ri+=1)for(double ro=1840;ro<=1900;ro+=3)for(int ph=0;ph<=4;++ph){double phase=180.*ph/(4*lcm);auto p=ring(ni,no,ri,ro,phase);
   if(!allcovered(p,995,24,180))continue;double lo=985,hi=1005;for(int k=0;k<9;++k){double m=(lo+hi)/2;if(allcovered(p,m,80,1080))hi=m;else lo=m;}
   // Include the limiting radius near the central station in the diagnostic.
   hi=std::max(hi,ri);out<<ni+no+1<<","<<ni<<","<<no<<","<<ri<<","<<ro<<","<<phase<<","<<hi<<"\n";
   double score=10000*(ni+no+1)+hi;if(score<best){best=score;bp=p;std::cout<<"refined n="<<p.size()<<" ri="<<ri<<" ro="<<ro<<" phase="<<phase<<" cover_diagnostic="<<hi<<std::endl;}
  }
 }
 std::ofstream coords(argc>2?argv[2]:"refined_points.csv");coords<<"x,y\n";for(auto p:bp)coords<<std::setprecision(17)<<p.x<<","<<p.y<<"\n";
}
