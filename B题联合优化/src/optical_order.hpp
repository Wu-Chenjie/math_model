#pragma once
#include "dynamic_selection.hpp"
namespace optical_order {
inline geo::Poly choose(const geo::Poly&p,geo::Pt now,const std::vector<dynamic_selection::Hypothesis>&original,double mixture=1.){
 if(p.empty())return p;
 auto fallback=p;if(geo::dist(now,fallback.back())<geo::dist(now,fallback.front()))std::reverse(fallback.begin(),fallback.end());
 if(original.empty())return fallback;
 auto hypotheses=original;
 if(mixture<1.){double mass=0;for(auto h:hypotheses)mass+=h.weight;for(auto &h:hypotheses)h.weight*=mixture/mass;for(auto q:p)hypotheses.push_back({q,1000,false,0,(1-mixture)/p.size()});}
 double total=0;for(auto h:hypotheses)total+=h.weight;double best=1e100;auto chosen=fallback;
 int n=p.size();std::vector<int>offsets{0,n-1};for(int i=1;i<=12;++i)offsets.push_back((i*n)/13);
 for(int reverse=0;reverse<2;++reverse)for(int offset:offsets){geo::Poly route;for(int k=0;k<n;++k){int j=reverse?(offset-k+n)%n:(offset+k)%n;route.push_back(p[j]);}
  std::vector<bool>done(hypotheses.size());int pending=hypotheses.size();double cost=0,expected=0;auto position=now;
  for(auto q:route){cost+=geo::dist(position,q)/5;position=q;
   for(int i=0;i<(int)hypotheses.size();++i)if(!done[i]&&geo::dist(q,hypotheses[i].z)<=20+1e-7){done[i]=true;--pending;expected+=hypotheses[i].weight/total*(cost+5);}
   if(!pending)break;cost+=3;
  }
  if(pending)continue;if(expected<best){best=expected;chosen=route;}
 }return chosen;
}
}
