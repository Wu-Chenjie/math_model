#pragma once
#include "adaptive_optical.hpp"
#include "optical_order.hpp"
#include <map>
#include <memory>
#define B_PREPARED_SWEEP 1
namespace optical_terminal {
// Geometric branch regions remain separate from finite ranking hypotheses.
// Prediction bins currently group noiseless bearings, not noisy report draws.
// Their angular envelope bounds geometry; branch probabilities remain approximate.
inline geo::Poly update(geo::Poly region,geo::Pt q,int outcome){
 if(outcome<10)return region;
 double angle=2.*(outcome-10)+1.;
 region=geo::observe(region,q,angle,2.005);
 region=geo::disk_clip(region,q,1500);
 auto u=geo::polar(1,angle);
 return geo::clip(region,u,geo::dot(u,q)+1500);
}
inline double expected(const geo::Poly& route,geo::Pt from,const std::vector<dynamic_selection::Hypothesis>& hypotheses){
 double total=0,cost=0,value=0;for(auto h:hypotheses)total+=h.weight;
 if(hypotheses.empty())return 0;
 std::vector<bool> done(hypotheses.size());size_t left=hypotheses.size();
 for(auto q:route){cost+=geo::dist(from,q)/5;from=q;
  for(size_t i=0;i<hypotheses.size();++i)if(!done[i]&&geo::dist(q,hypotheses[i].z)<=20+1e-7){done[i]=true;--left;value+=hypotheses[i].weight/total*(cost+5);}
  if(!left)return value;cost+=3;
 }
 throw std::runtime_error("terminal route does not cover conditional hypotheses");
}
class PreparedSweep {
 geo::Poly points;
 std::vector<uint64_t> hits;
 std::vector<std::vector<double>>travel;
 std::vector<double>weights;
 public:
 PreparedSweep(const geo::Poly& p,const std::vector<dynamic_selection::Hypothesis>& h):points(p){
  if(p.empty()||h.empty()||h.size()>63)throw std::invalid_argument("invalid prepared sweep");
  for(auto x:h)weights.push_back(x.weight);
  hits.assign(p.size(),0);travel.assign(p.size(),std::vector<double>(p.size()));
  for(size_t i=0;i<p.size();++i){for(size_t j=0;j<h.size();++j)if(geo::dist(p[i],h[j].z)<=20+1e-7)hits[i]|=uint64_t(1)<<j;
   for(size_t j=0;j<p.size();++j)travel[i][j]=geo::dist(p[i],p[j])/5;
  }
 }
 double value(uint64_t mask,geo::Pt now,bool match_entry=true)const{
  if(!mask)return 0;
  if(mask>>weights.size())throw std::invalid_argument("invalid sweep mask");
  double total=0;for(size_t i=0;i<weights.size();++i)if(mask>>i&1)total+=weights[i];
  int n=points.size();bool flip=match_entry&&geo::dist(now,points.back())<geo::dist(now,points.front());
  std::vector<int>offsets{0,n-1};for(int i=1;i<=12;++i)offsets.push_back(i*n/13);
  std::vector<double>entry;for(auto p:points)entry.push_back(geo::dist(now,p)/5);
  double best=INFINITY;
  for(int reverse=0;reverse<2;++reverse)for(int offset:offsets){
   uint64_t remaining=mask;double cost=0,value=0;int previous=-1;
   for(int k=0;k<n;++k){int logical=reverse?(offset-k+n)%n:(offset+k)%n;int j=flip?n-1-logical:logical;
    cost+=previous<0?entry[j]:travel[previous][j];previous=j;
    uint64_t found=remaining&hits[j];remaining&=~found;
    while(found){int i=__builtin_ctzll(found);value+=weights[i]/total*(cost+5);found&=found-1;}
    if(!remaining)break;cost+=3;
   }
   if(!remaining&&value<best)best=value;
  }
  if(!std::isfinite(best))throw std::runtime_error("terminal route does not cover conditional hypotheses");
  return best;
 }
};
class Contexts {
 struct State {geo::Poly region;std::unique_ptr<PreparedSweep>sweep;std::map<std::pair<int,int>,int>children;};
 std::vector<State> states;
 const std::vector<geo::Pt>&locations;
 const std::vector<bool>&sensing;
 const std::vector<dynamic_selection::Hypothesis>&hypotheses;
 geo::Pt first;double angle;bool match_entry;
 public:
 Contexts(const geo::Poly& p,const std::vector<geo::Pt>& q,const std::vector<bool>& m,const std::vector<dynamic_selection::Hypothesis>& h,geo::Pt f,double a,bool match=false):locations(q),sensing(m),hypotheses(h),first(f),angle(a),match_entry(match){states.push_back({p,{}, {}});}
 int advance(int context,int action,int outcome){
  // Negative readings and failed clears do not yet have a continuous set update.
  if(!sensing.at(action)||outcome<10)return context;
  auto key=std::make_pair(action,outcome);auto it=states.at(context).children.find(key);
  if(it!=states[context].children.end())return it->second;
  auto region=update(states[context].region,locations.at(action),outcome);
  if(region.empty())throw std::runtime_error("empty predicted continuous region");
  int id=states.size();states[context].children[key]=id;states.push_back({std::move(region),{}, {}});return id;
 }
 double value(uint64_t mask,geo::Pt now,int context){
  auto& state=states.at(context);
  if(!state.sweep)state.sweep=std::make_unique<PreparedSweep>(adaptive_optical::cover(state.region,first,angle),hypotheses);
  return state.sweep->value(mask,now,match_entry);
 }
};
}
