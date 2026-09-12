#pragma once
#include "certified_route.hpp"
#include <random>
namespace new_route {
// Deterministic, non-neural destroy/repair prototype. This is not NLNS or LKH.
inline std::vector<int> repair(const cert_route::Problem&p,std::vector<int> r,std::vector<int> missing){
 while(!missing.empty()){
  int chosen=-1,at=-1;double regret=-1,bestCost=1e100;
  for(int a=0;a<(int)missing.size();++a){double best=1e100,second=1e100;int index=0;
   for(int j=0;j<=(int)r.size();++j){auto q=r;q.insert(q.begin()+j,missing[a]);double c=cert_route::length(p,q);if(c<best){second=best;best=c;index=j;}else second=std::min(second,c);}
   double diff=second<1e99?second-best:0;
   if(diff>regret+1e-8||(std::abs(diff-regret)<1e-8&&best<bestCost)){regret=diff;bestCost=best;chosen=a;at=index;}
  }
  r.insert(r.begin()+at,missing[chosen]);missing.erase(missing.begin()+chosen);
 }return r;
}
inline cert_route::Solution solve(const cert_route::Problem&p){
 auto s=cert_route::solve(p);int n=p.start.size();if(s.exact)return s;
 std::mt19937 rng(120926+n);
 for(int iteration=0;iteration<10;++iteration){
  auto r=s.path;std::vector<int>missing;int k=3+iteration%4;
  for(int t=0;t<k;++t){int j=(iteration%2==0)?int(rng()%r.size()):int((iteration+t)%r.size());missing.push_back(r[j]);r.erase(r.begin()+j);}
  r=repair(p,r,missing);
  if(cert_route::length(p,r)<s.upper-1e-7||iteration%3==0)cert_route::improve(p,r,true);
  double cost=cert_route::length(p,r);if(cost<s.upper-1e-7){s.path=r;s.upper=cost;}
 }
 s.local_optimal=cert_route::improve(p,s.path,true);s.upper=cert_route::length(p,s.path);return s;
}
}
