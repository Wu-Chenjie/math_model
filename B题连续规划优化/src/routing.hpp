#pragma once
#include "geometry.hpp"
#include <numeric>
namespace route {
inline double length(geo::Pt start,const geo::Poly&p,const std::vector<int>&r){double d=0;for(int i:r){d+=geo::dist(start,p[i]);start=p[i];}return d;}
inline std::vector<int> nearest(geo::Pt start,const geo::Poly&p,int first=-1){
 std::vector<int> r;std::vector<bool>used(p.size());
 if(first>=0){r.push_back(first);used[first]=true;start=p[first];}
 while(r.size()<p.size()){int best=-1;double d=1e100;for(int i=0;i<(int)p.size();++i)if(!used[i]&&geo::dist(start,p[i])<d){d=geo::dist(start,p[i]);best=i;}r.push_back(best);used[best]=true;start=p[best];}return r;
}
inline void two_opt(geo::Pt start,const geo::Poly&p,std::vector<int>&r){
 for(int iter=0;iter<100;++iter){double best=-1e-7;int bi=-1,bj=-1;
  for(int i=0;i<(int)r.size()-1;++i)for(int j=i+1;j<(int)r.size();++j){auto a=i?p[r[i-1]]:start;double delta=geo::dist(a,p[r[j]])-geo::dist(a,p[r[i]]);
   if(j+1<(int)r.size())delta+=geo::dist(p[r[i]],p[r[j+1]])-geo::dist(p[r[j]],p[r[j+1]]);
   if(delta<best){best=delta;bi=i;bj=j;}}
  if(bi<0)break;std::reverse(r.begin()+bi,r.begin()+bj+1);
 }
}
inline std::vector<int> optimize(geo::Pt start,const geo::Poly&p){auto best=nearest(start,p);two_opt(start,p,best);double cost=length(start,p,best);
 // Deterministic starts: all possible first nodes, capped only by small problem size.
 for(int first=0;first<(int)p.size();++first){auto r=nearest(start,p,first);two_opt(start,p,r);double c=length(start,p,r);if(c<cost-1e-7){cost=c;best=r;}}
 return best;
}
}
