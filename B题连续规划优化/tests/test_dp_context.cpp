#include "../src/belief_dp.hpp"
#include <cassert>
#include <iostream>
#include <random>
double exhaustive(const belief_dp::Model& m,uint64_t mask,int at,int depth,bool tuned,int context){
#ifdef B_CONTEXT_TERMINAL
 double best=m.terminal_context(mask,at,context);
 if(!depth)return best;double total=0;for(int i=0;i<(int)m.weights.size();++i)if(mask>>i&1)total+=m.weights[i];
 for(int a=0;a<(int)m.actions.size();++a){auto x=m.actions[a];double cost=m.travel[at][a]+(x.measure&&!tuned?1:0);std::map<int,uint64_t> groups;
  for(int i=0;i<(int)m.weights.size();++i)if(mask>>i&1){cost+=m.weights[i]/total*x.seconds[i];groups[x.outcome[i]]|=uint64_t(1)<<i;}
  for(auto [out,sub]:groups)if(out>=0){double w=0;for(int i=0;i<(int)m.weights.size();++i)if(sub>>i&1)w+=m.weights[i];cost+=w/total*exhaustive(m,sub,a,depth-1,tuned||x.measure,m.advance(context,a,out));}
  best=std::min(best,cost);
 }return best;
#else
 return 0;
#endif
}
int main(){
#ifndef B_CONTEXT_TERMINAL
 std::cerr<<"FAIL DP cannot distinguish continuous regions sharing a particle mask\n";return 1;
#else
 std::mt19937 random(613);
 for(int trial=0;trial<100;++trial){belief_dp::Model m;m.weights={1,2,3};m.travel.assign(4,std::vector<double>(4,0));
  for(int a=0;a<3;++a){belief_dp::Action x;x.measure=a!=2;for(int i=0;i<3;++i){x.outcome.push_back(int(random()%4)-1);x.seconds.push_back(3+a);}m.actions.push_back(x);}
  m.terminal=[](uint64_t,int){return 100.;};
  m.advance=[](int c,int a,int out){return c*17+(a+1)*4+out+1;};
  m.terminal_context=[](uint64_t mask,int at,int context){return context?double(5+((context*13+at+mask)%29)):100.;};
  auto r=belief_dp::solve(m,3,false,10000);
  assert(r.exact&&std::abs(r.value-exhaustive(m,7,3,3,false,0))<1e-9);
 }
 std::cout<<"PASS context-aware DP: 100 exhaustive history-dependent comparisons\n";
#endif
}
