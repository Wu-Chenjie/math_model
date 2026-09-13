#pragma once
#include "bearing_types.hpp"
#include <numeric>
#include <cstdint>
#include <stdexcept>
#define B_SEARCH_ORDER 1
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
// Minimize expected time to first successful clear, retaining the entire cover.
// The cell-center mixture is a ranking regularizer, never a geometric proof.
inline geo::Poly search(const geo::Poly&p,geo::Pt now,const std::vector<dynamic_selection::Hypothesis>&original,double mixture=.1){
 if(p.empty()||original.empty())return choose(p,now,original);
 if(!(mixture>=0&&mixture<=1))throw std::invalid_argument("invalid search mixture");
 auto h=original;double mass=0;for(auto x:h)mass+=x.weight;
 for(auto &x:h)x.weight*=(1-mixture)/mass;
 if(mixture>0)for(auto q:p)h.push_back({q,1000,false,0,mixture/p.size()});
 const int n=p.size(),chunks=(h.size()+63)/64;
 std::vector<std::vector<uint64_t>> hits(n,std::vector<uint64_t>(chunks));
 std::vector<std::vector<double>> travel(n,std::vector<double>(n));std::vector<double>entry(n);
 for(int i=0;i<n;++i){entry[i]=geo::dist(now,p[i])/5;for(int j=0;j<n;++j)travel[i][j]=geo::dist(p[i],p[j])/5;
  for(size_t j=0;j<h.size();++j)if(geo::dist(p[i],h[j].z)<=20+1e-7)hits[i][j/64]|=uint64_t(1)<<(j%64);
 }
 std::vector<uint64_t>full(chunks,~uint64_t(0));if(h.size()%64)full.back()=(uint64_t(1)<<(h.size()%64))-1;
 auto cost=[&](const std::vector<int>&order)->double{auto remaining=full;size_t pending=h.size();double elapsed=0,expected=0;int previous=-1;
  for(int j:order){elapsed+=previous<0?entry[j]:travel[previous][j];previous=j;
   for(int k=0;k<chunks;++k){uint64_t found=remaining[k]&hits[j][k];remaining[k]&=~found;
    while(found){int bit=__builtin_ctzll(found);expected+=h[k*64+bit].weight*(elapsed+5);--pending;found&=found-1;}
   }if(!pending)return expected;elapsed+=3;
  }return INFINITY;
 };
 auto cyclic=choose(p,now,h);std::vector<int>best_order;std::vector<bool>mapped(n);
 for(auto q:cyclic)for(int i=0;i<n;++i)if(!mapped[i]&&geo::dist(q,p[i])<1e-8){mapped[i]=true;best_order.push_back(i);break;}
 if(best_order.size()!=p.size())throw std::runtime_error("search route permutation mismatch");
 double best=cost(best_order);
 for(double power:{.5,1.,1.5}){std::vector<int>order;std::vector<bool>used(n);auto remaining=full;int previous=-1;
  for(int step=0;step<n;++step){int chosen=-1;double score=-1;
   for(int j=0;j<n;++j)if(!used[j]){double probability=0;
    for(int k=0;k<chunks;++k){uint64_t found=remaining[k]&hits[j][k];while(found){int bit=__builtin_ctzll(found);probability+=h[k*64+bit].weight;found&=found-1;}}
    double seconds=3+(previous<0?entry[j]:travel[previous][j]);double value=(probability+1e-12)/std::pow(seconds,power);
    if(value>score){score=value;chosen=j;}
   }used[chosen]=true;order.push_back(chosen);previous=chosen;for(int k=0;k<chunks;++k)remaining[k]&=~hits[chosen][k];
  }double value=cost(order);if(value<best){best=value;best_order=std::move(order);}
 }
 for(int pass=0;pass<2;++pass){auto chosen=best_order;double improved=best;
  for(int i=0;i<n-1;++i)for(int j=i+1;j<n;++j){auto candidate=best_order;std::reverse(candidate.begin()+i,candidate.begin()+j+1);double value=cost(candidate);if(value<improved-1e-10){improved=value;chosen=std::move(candidate);}}
  if(improved>=best-1e-10)break;best=improved;best_order=std::move(chosen);
 }
 geo::Poly route;for(int i:best_order)route.push_back(p[i]);return route;
}
}
