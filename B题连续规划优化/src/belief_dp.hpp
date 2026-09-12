#pragma once
#define B_CONTEXT_TERMINAL 1
#include <vector>
#include <functional>
#include <cstdint>
#include <stdexcept>
#include <map>
#include <tuple>
#include <cmath>
#include <algorithm>
namespace belief_dp {
struct Action {bool measure;std::vector<int>outcome;std::vector<double>seconds;};
struct Model {std::vector<double>weights;std::vector<Action>actions;std::vector<std::vector<double>>travel;std::function<double(uint64_t,int)>terminal;std::function<int(int,int,int)>advance;std::function<double(uint64_t,int,int)>terminal_context;};
struct Result {int action=-1;double value=0;int expanded=0;bool exact=false,budget_hit=false;std::vector<double>action_values;};
inline Result solve(const Model&m,int depth,bool tuned,int limit){
 const int n=m.weights.size(),a=m.actions.size();
 if(n<1||n>63||depth<0||depth>5||limit<0||!m.terminal||m.travel.size()!=size_t(a+1))throw std::invalid_argument("invalid DP dimensions");
 for(double w:m.weights)if(!(w>0)||!std::isfinite(w))throw std::invalid_argument("invalid hypothesis weight");
 for(const auto &row:m.travel){if(row.size()!=size_t(a+1))throw std::invalid_argument("invalid travel matrix");for(double x:row)if(x<0||!std::isfinite(x))throw std::invalid_argument("invalid travel cost");}
 for(const auto &x:m.actions){if(x.outcome.size()!=size_t(n)||x.seconds.size()!=size_t(n))throw std::invalid_argument("invalid action dimensions");for(double c:x.seconds)if(c<0||!std::isfinite(c))throw std::invalid_argument("invalid action cost");}
 if(bool(m.advance)!=bool(m.terminal_context))throw std::invalid_argument("both context callbacks required");
 Result result;result.action_values.assign(a,INFINITY);std::map<std::tuple<uint64_t,int,int,bool,int>,std::pair<double,int>>memo;
 std::map<std::tuple<uint64_t,int,int>,double>leaves;std::map<uint64_t,double>masses;
 auto mass=[&](uint64_t mask){auto it=masses.find(mask);if(it!=masses.end())return it->second;double w=0;for(int i=0;i<n;++i)if(mask>>i&1)w+=m.weights[i];masses[mask]=w;return w;};
 auto terminal=[&](uint64_t mask,int at,int context){auto key=std::make_tuple(mask,at,context);auto it=leaves.find(key);if(it!=leaves.end())return it->second;double v=m.terminal_context?m.terminal_context(mask,at,context):m.terminal(mask,at);if(v<0||!std::isfinite(v))throw std::invalid_argument("invalid terminal policy cost");leaves[key]=v;return v;};
 std::function<std::pair<double,int>(uint64_t,int,int,bool,int)>value;
 value=[&](uint64_t mask,int at,int h,bool tunedNow,int context){
  auto key=std::make_tuple(mask,at,h,tunedNow,context);auto it=memo.find(key);if(it!=memo.end())return it->second;
  std::pair<double,int>best{terminal(mask,at,context),-1};if(h==0)return best;
  if(result.expanded>=limit){result.budget_hit=true;return best;}++result.expanded;
  double total=mass(mask);
  for(int j=0;j<a;++j){const auto &act=m.actions[j];std::map<int,uint64_t>groups;
   double cost=m.travel[at][j]+(act.measure&&!tunedNow?1.:0.);
   for(int i=0;i<n;++i)if(mask>>i&1){cost+=m.weights[i]/total*act.seconds[i];groups[act.outcome[i]]|=uint64_t(1)<<i;}
   // No state reduction and no terminal success: extra action is uninformative.
   if(!m.advance&&groups.size()==1&&groups.begin()->first>=0)continue;
   for(auto [out,sub]:groups)if(out>=0)cost+=mass(sub)/total*value(sub,j,h-1,tunedNow||act.measure,m.advance?m.advance(context,j,out):0).first;
   if(at==a&&h==depth)result.action_values[j]=cost;
   if(cost<best.first-1e-10)best={cost,j};
  }
  memo[key]=best;return best;
 };
 auto best=value((uint64_t(1)<<n)-1,a,depth,tuned,0);result.value=best.first;result.action=best.second;result.exact=!result.budget_hit;return result;
}
}
