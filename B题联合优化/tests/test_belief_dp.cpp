#include "../src/belief_dp.hpp"
#include <cassert>
#include <iostream>
#include <random>
#include <map>
using belief_dp::Model;using belief_dp::Action;
double brute(const Model&m,uint64_t mask,int at,int h,bool tuned){
 double best=m.terminal(mask,at);if(h==0)return best;
 double mass=0;for(int i=0;i<(int)m.weights.size();++i)if(mask>>i&1)mass+=m.weights[i];
 for(int a=0;a<(int)m.actions.size();++a){auto &x=m.actions[a];double cost=m.travel[at][a]+(x.measure&&!tuned?1:0);std::map<int,uint64_t>groups;
  for(int i=0;i<(int)m.weights.size();++i)if(mask>>i&1){cost+=m.weights[i]/mass*x.seconds[i];groups[x.outcome[i]]|=uint64_t(1)<<i;}
  if(groups.size()==1&&groups.begin()->first>=0)continue;
  for(auto [out,sub]:groups)if(out>=0){double w=0;for(int i=0;i<(int)m.weights.size();++i)if(sub>>i&1)w+=m.weights[i];cost+=w/mass*brute(m,sub,a,h-1,tuned||x.measure);}
  best=std::min(best,cost);
 }return best;
}
int main(){
 Model m;m.weights={.5,.5};m.actions={{true,{10,11},{5,5}},{false,{-1,0},{5,3}},{false,{0,-1},{3,5}}};m.travel.assign(4,std::vector<double>(4));
 m.travel[3][1]=m.travel[3][2]=10.;m.terminal=[](uint64_t mask,int){return mask==3?100.:5.;};
 auto result=belief_dp::solve(m,2,false,10000);
 assert(result.action==0&&std::abs(result.value-11)<1e-9); // sensing + one switch + adaptive clear
 assert(result.exact&&result.expanded>0);
 assert(result.action_values.size()==m.actions.size());assert(std::abs(result.action_values[0]-11)<1e-9);assert(result.action_values[1]>result.action_values[0]);
 auto zero=belief_dp::solve(m,0,false,10000);assert(zero.action==-1&&zero.value==100);
 auto limited=belief_dp::solve(m,2,false,0);assert(limited.action==-1&&!limited.exact&&limited.budget_hit);
 // A near response includes immediate optical success, with no continuation.
 Model near=m;near.actions={{true,{-1,-1},{10,10}}};near.travel.assign(2,std::vector<double>(2));assert(belief_dp::solve(near,2,false,100).value==11);
 Model clear=m;clear.weights={.99,.01};clear.actions.erase(clear.actions.begin());clear.travel.assign(3,std::vector<double>(3));assert(belief_dp::solve(clear,1,true,100).action==0);
 clear.weights={.01,.99};assert(belief_dp::solve(clear,1,true,100).action==1);
 // No-signal (outcome0) retains a genuine branch, never terminal success.
 Model dropout=m;dropout.actions[0].outcome={0,10};assert(belief_dp::solve(dropout,2,false,100).value==11);
 std::mt19937 rng(12);
 for(int trial=0;trial<100;++trial){Model t;t.weights={1.,2.,3.};int n=4;t.travel.assign(n+1,std::vector<double>(n+1));
  for(auto &row:t.travel)for(auto &x:row)x=rng()%20;
  for(int a=0;a<n;++a){Action x;x.measure=(a%2==0);for(int i=0;i<3;++i){x.outcome.push_back(int(rng()%4)-1);x.seconds.push_back(x.measure?5:3);}t.actions.push_back(x);}
  t.terminal=[](uint64_t mask,int at){return 20.+3*__builtin_popcountll(mask)+at;};
  auto r=belief_dp::solve(t,3,false,10000);assert(r.exact);assert(std::abs(r.value-brute(t,7,n,3,false))<1e-9);
 }
 bool invalid=false;try{Model bad=m;bad.weights[0]=-1;belief_dp::solve(bad,2,true,100);}catch(const std::invalid_argument&){invalid=true;}assert(invalid);
 std::cout<<"PASS Bellman: information, priors, near/no-signal, tuning, depth/budget; 100 exhaustive comparisons\n";
}
