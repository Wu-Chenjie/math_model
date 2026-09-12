#pragma once
#include "geometry.hpp"
#include "routing.hpp"
#include "certified_route.hpp"
#include "position_uncertainty.hpp"
#include "lns.hpp"
#include "active.hpp"
#include "dynamic_selection.hpp"
#include "optical_order.hpp"
#include "discovery.hpp"
#include "adaptive_optical.hpp"
#include "optical_portfolio.hpp"
#include "../review/certified_layout21_hex.hpp"
#include <array>
#include <stdexcept>
using geo::Pt;using geo::Poly;
struct Reading {int kind=0;double angle=0;}; // no_signal=0, near=1, direction=2
struct Sensor {virtual Reading measure(Pt,int)=0;virtual bool clear(Pt,int)=0;virtual void audit(int,const Poly&){};virtual void phase(int){};virtual ~Sensor()=default;};
struct Track {Poly p;Pt first;double angle=0;int obs=0;bool cleared=false;std::vector<dynamic_selection::Event>history;int dynamic_used=0,aux_used=0;};
struct Options {double spacing=950,early=35;bool square=false,dynamic=true;int routing=0;double shiftA=0,shiftB=0;bool shifted=false,includeOrigin=true,opportunistic=false;int fixedLayout=0;double secondA=750,secondB=300,eta=0;bool stop_when_found16=false;int route_model=0;bool use_lns=false;int active_mode=0;int dynamic_depth=0,dp_node_limit=6000;bool joint_actions=false;int auxiliary=0,aux_limit=4;double start_residual=0;bool retreat=false,candidate_menu=false,complete_source=false,direct_optical=false,optical_rotate=false;int planning_samples=32;double q3_radius=1200;bool clear_neighborhood=false,defer_single=false,weighted_optical=false;double optical_weight=1,immediate_fee_weight=0,discovery_weight=0;int dynamic_limit=6;bool adaptive_optical=false;int terminal_mode=0;bool variable_optical=false;int optical_search=0;bool budget_aware=false;int refinement=0;int bearing_bin=2;int optical_portfolio=0;bool shortcut=false;};
class Policy {
 Sensor& io;int problem;Options opt;std::array<Track,21> t;bool auxiliary_busy=false;discovery::Belief unseen;
 public:Pt pos;int channel=1,cleared=0,fallbacks=0,plans=0,exact_plans=0,local_plans=0,nonlocal_plans=0,covered_skips=0;double max_route_gap=0,total_route_gap=0,total_route_upper=0,max_relative_gap=0;std::string certificate="incomplete";
 int dynamic_plans=0,dynamic_actions=0,dynamic_fallbacks=0,dp_expanded=0,dp_budget_hits=0;
 int auxiliary_calls=0,auxiliary_positive=0,joint_steps=0;
 Policy(Sensor& s,int prob,Options o={}):io(s),problem(prob),opt(o){if(opt.discovery_weight>0)unseen=discovery::Belief(prob);}
 Reading measure(Pt p,int k){auto r=io.measure(p,k);pos=p;channel=k;
  if(opt.dynamic_depth>0)t[k].history.push_back({p,r.kind,r.angle});
  if(r.kind==1){if(!clear(p,k))throw std::runtime_error("near followed by failed clear");}
  else if(r.kind==2){auto &a=t[k];if(a.obs==0){a.p=geo::outer_disk({0,0},1800);a.first=p;a.angle=r.angle;}
   if(opt.eta>0)a.p=position_error::update(a.p,p,r.angle,opt.eta);
   else {a.p=geo::observe(a.p,p,r.angle);a.p=geo::disk_clip(a.p,p,1500);}
   // Valid axial bound additionally prevents circumscribed-disk overshoot along bearing.
   Pt u=geo::polar(1,r.angle);a.p=geo::clip(a.p,u,geo::dot(u,p)+1500+opt.eta);
   ++a.obs;if(a.p.empty())throw std::runtime_error("empty feasible region");io.audit(k,a.p);}
  if(opt.auxiliary>=3&&!auxiliary_busy)supplement(p,k);
  return r;
 }
 bool clear(Pt p,int k){bool ok=io.clear(p,k);pos=p;if(opt.dynamic_depth>0)t[k].history.push_back({p,ok?4:3,0});if(ok&&!t[k].cleared){t[k].cleared=true;++cleared;}if(opt.auxiliary>=3&&!auxiliary_busy)supplement(p,k);return ok;}
 void optical(int k){io.phase(2);++fallbacks;auto &a=t[k];Pt u=geo::polar(1,a.angle),v={-u.y,u.x};
  double xmin=1e99,xmax=-1e99,ymin=1e99,ymax=-1e99;
  for(auto p:a.p){Pt d=p-a.first;double x=geo::dot(d,u),y=geo::dot(d,v);xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);}
  double step=opt.eta>0?position_error::grid_side(opt.eta):28;
  int nx=std::max(1,(int)ceil((xmax-xmin)/step)),ny=std::max(1,(int)ceil((ymax-ymin)/step));
  Poly route;for(int i=0;i<nx;++i)for(int jj=0;jj<ny;++jj){int j=i%2?ny-1-jj:jj;route.push_back(a.first+u*(xmin+(i+.5)*(xmax-xmin)/nx)+v*(ymin+(j+.5)*(ymax-ymin)/ny));}
  if(opt.adaptive_optical&&opt.eta==0){auto candidate=adaptive_optical::cover(a.p,a.first,a.angle);if(!candidate.empty())route=candidate;}
  if(opt.variable_optical&&opt.eta==0)route=adaptive_optical::variable_cover(a.p,a.first,a.angle);
  if(geo::dist(pos,route.back())<geo::dist(pos,route.front()))std::reverse(route.begin(),route.end());
  if(opt.optical_rotate){size_t best=0;for(size_t i=1;i<route.size();++i)if(geo::dist(pos,route[i])<geo::dist(pos,route[best]))best=i;std::rotate(route.begin(),route.begin()+best,route.end());}
  if(opt.weighted_optical&&opt.eta==0)route=optical_order::choose(route,pos,dynamic_selection::make_hypotheses(a.p,a.history,problem,63),opt.optical_weight);
  if(opt.optical_search&&opt.eta==0)route=optical_order::search(route,pos,dynamic_selection::make_hypotheses(a.p,a.history,problem,63),opt.optical_search==1?0:opt.optical_search==2?.1:.3);
  if(opt.optical_portfolio&&opt.eta==0){
   auto h=dynamic_selection::make_hypotheses(a.p,a.history,problem,63);
   auto candidate=adaptive_optical::variable_cover(a.p,a.first,a.angle);
   if(geo::dist(pos,candidate.back())<geo::dist(pos,candidate.front()))std::reverse(candidate.begin(),candidate.end());
   candidate=optical_order::choose(candidate,pos,h);
   if(opt.optical_portfolio==2)candidate=optical_order::search(candidate,pos,h,.1);
   double fraction=opt.optical_portfolio==1?.05:opt.optical_portfolio==2?.1:opt.optical_portfolio==3?.2:0;
   route=optical_portfolio::choose(route,candidate,pos,h,fraction,100*fraction);
  }
  for(auto p:route)if(clear(p,k))return;
  throw std::runtime_error("continuous optical coverage exhausted without success");
 }
 void locate(int k){io.phase(1);auto &a=t[k];if(a.cleared)return;
  if(opt.dynamic_depth>0&&opt.eta==0){
   for(int step=a.dynamic_used;step<opt.dynamic_limit&&!a.cleared;++step){
    int depth=opt.budget_aware?dynamic_selection::remaining_depth(opt.dynamic_depth,opt.dynamic_limit,a.dynamic_used):opt.dynamic_depth;
    auto decision=dynamic_selection::plan(a.p,pos,a.first,a.angle,a.history,problem,depth,channel==k,opt.dp_node_limit,opt.retreat,opt.planning_samples,opt.clear_neighborhood,opt.terminal_mode,opt.refinement,opt.bearing_bin);
    ++dynamic_plans;dp_expanded+=decision.expanded;dp_budget_hits+=decision.budget_hit;
    if(!decision.available)break;
    ++dynamic_actions;++a.dynamic_used;if(decision.measure)measure(decision.point,k);else clear(decision.point,k);
   }
   if(a.cleared)return;++dynamic_fallbacks;
  }
  if(opt.direct_optical)optical(k);else locate_baseline(k);
 }
 void locate_baseline(int k){auto &a=t[k];if(a.cleared)return;
  if(opt.opportunistic&&a.obs==1){Pt u=geo::polar(1,a.angle);if(std::abs(geo::cross(u,pos-a.first))>=50){measure(pos,k);if(a.cleared)return;}}
  if(a.obs==1){Pt u=geo::polar(1,a.angle),v={-u.y,u.x};Pt q1=a.first+u*opt.secondA+v*opt.secondB,q2=a.first+u*opt.secondA-v*opt.secondB;
   if(geo::dist(pos,q2)<geo::dist(pos,q1))std::swap(q1,q2);
   if(opt.active_mode)q1=active::choose(a.p,pos,a.first,a.angle,opt.secondA,opt.secondB,opt.active_mode);
   auto r=measure(q1,k);if(a.cleared)return;
   if(r.kind==0){measure(q2,k);if(a.cleared)return;}
  }
  for(int attempt=0;attempt<3&&!a.cleared;++attempt){auto c=geo::mec(a.p);
   if(c.r<=opt.early || c.r<=20-opt.eta-1e-6){if(clear(c.c,k))return;}
   if(a.obs<2)break;
   Pt q=c.c;
   if(geo::dist(pos,q)<1){Pt u=geo::polar(1,a.angle);q=q+Pt{-u.y,u.x}*(attempt%2?-50:50);}
   auto r=measure(q,k);if(a.cleared)return;
   if(r.kind==0){Pt u=geo::polar(1,a.angle),v={-u.y,u.x};measure(c.c+v*50,k);if(a.cleared)return;}
  }
  if(!a.cleared)optical(k);
 }
 Poly covering_points(){
  if(problem==3&&opt.q3_radius!=1200){Poly p{{0,0}};for(int i=0;i<6;++i)p.push_back(geo::polar(opt.q3_radius,60*i));return p;}
  if(problem==4&&opt.fixedLayout==21){Poly p;for(auto x:certified_layout21::points)p.push_back({x.x,x.y});return p;}
  if(problem==3||!opt.shifted)return geo::coverage(problem,opt.square?600:opt.spacing,opt.square);
  Poly points;if(opt.includeOrigin)points.push_back({0,0});double h=opt.spacing;auto v=[&](int i,int j){return Pt{h*(i+opt.shiftA+.5*(j+opt.shiftB)),h*sqrt(3.)/2*(j+opt.shiftB)};};
  for(int i=-6;i<6;++i)for(int j=-6;j<6;++j){Pt a=v(i,j),b=v(i+1,j),c=v(i,j+1),d=v(i+1,j+1);
   for(auto triangle:{Poly{a,b,c},Poly{d,c,b}})if(geo::meets_disk(triangle,1800))for(auto q:triangle){bool duplicate=false;for(auto p:points)if(geo::dist(p,q)<1e-6)duplicate=true;if(!duplicate)points.push_back(q);}}
  return points;
 }
 void supplement(Pt q,int exclude=0){
  if(opt.auxiliary==0||opt.eta!=0||auxiliary_busy)return;
  auxiliary_busy=true;
  int start=channel;
  for(int j=0;j<20;++j){int k=1+(start-1+j)%20;auto &a=t[k];
   if(k==exclude||a.cleared||a.obs==0||a.aux_used>=opt.aux_limit)continue;
   auto c=geo::mec(a.p);if(c.r<=20||geo::dist(q,c.c)>1000)continue;
   auto u=geo::polar(1,a.angle);if(std::abs(geo::cross(u,q-a.first))<50)continue;
   bool repeated=false;for(auto e:a.history)if(e.kind<=2&&geo::dist(e.q,q)<1e-6)repeated=true;if(repeated)continue;
   if(opt.auxiliary>=4){auto sample=dynamic_selection::make_hypotheses(a.p,a.history,problem,32);double total=0,heard=0;for(auto h:sample){total+=h.weight;if(dynamic_selection::receives(h,q))heard+=h.weight;}if(total==0||heard<.6*total)continue;}
   ++a.aux_used;++auxiliary_calls;auto r=measure(q,k);if(r.kind>0)++auxiliary_positive;
  }
  auxiliary_busy=false;
 }
 void scan(Pt q){io.phase(0);int start=channel;for(int a=0;a<20;++a){int k=1+(start-1+a)%20;if(!t[k].cleared&&t[k].obs==0)measure(q,k);}supplement(q);if(opt.discovery_weight>0)unseen.negative_scan(q);}
 int known()const{int n=0;for(int k=1;k<=20;++k)n+=(t[k].cleared||t[k].obs>0);return n;}
 double scan_fee()const{int n=0;for(int k=1;k<=20;++k)if(!t[k].cleared&&t[k].obs==0)++n;return n?6*n-(!t[channel].cleared&&t[channel].obs==0?1:0):0;}
 double service_distance(Pt from,Pt center,int kind){
  if(opt.route_model!=2||kind<0||t[kind].obs!=1)return geo::dist(from,center);
  auto &tr=t[kind];auto u=geo::polar(1,tr.angle);Pt v={-u.y,u.x};auto a=tr.first+u*opt.secondA+v*opt.secondB,b=tr.first+u*opt.secondA-v*opt.secondB;
  // Entry side follows the production nearest-side rule. The exit remains
  // a belief-center approximation, not a secretly observed source position.
  Pt entry=geo::dist(from,a)<=geo::dist(from,b)?a:b;
  return geo::dist(from,entry)+geo::dist(entry,center);
 }
 void joint_run(const Poly&points){std::vector<bool>visited(points.size());
  while(cleared<16){Poly nodes;std::vector<int> kind;std::vector<dynamic_selection::Choice>choices;
   bool complete_discovery=opt.stop_when_found16&&known()==16;
   for(int i=0;i<(int)points.size();++i)if(!visited[i]){if(complete_discovery){visited[i]=true;++covered_skips;}else{nodes.push_back(points[i]);kind.push_back(-1-i);choices.push_back({});}}
   bool coverage_left=!nodes.empty();
   for(int k=1;k<=20;++k)if(t[k].obs&&!t[k].cleared){
    if(opt.defer_single&&coverage_left&&t[k].obs==1)continue;
    dynamic_selection::Choice decision;auto &a=t[k];
    if(opt.joint_actions&&opt.dynamic_depth>0&&opt.eta==0&&a.dynamic_used<opt.dynamic_limit){
     int depth=opt.budget_aware?dynamic_selection::remaining_depth(opt.dynamic_depth,opt.dynamic_limit,a.dynamic_used):opt.dynamic_depth;
     decision=dynamic_selection::plan(a.p,pos,a.first,a.angle,a.history,problem,depth,channel==k,opt.dp_node_limit,opt.retreat,opt.planning_samples,opt.clear_neighborhood,opt.terminal_mode,opt.refinement,opt.bearing_bin);
     ++dynamic_plans;dp_expanded+=decision.expanded;dp_budget_hits+=decision.budget_hit;
    }
    nodes.push_back(decision.available&&!opt.candidate_menu?decision.point:geo::mec(a.p).c);kind.push_back(k);choices.push_back(decision);
   }
   if(nodes.empty())break;std::vector<int>order;
   if(opt.route_model){cert_route::Problem task;int n=nodes.size();task.start.resize(n);task.edge.assign(n,std::vector<double>(n));
    for(int j=0;j<n;++j){task.start[j]=opt.joint_actions?geo::dist(pos,nodes[j]):service_distance(pos,nodes[j],kind[j]);for(int i=0;i<n;++i)if(i!=j)task.edge[i][j]=opt.joint_actions?geo::dist(nodes[i],nodes[j]):service_distance(nodes[i],nodes[j],kind[j]);}
    if(opt.candidate_menu){auto cost=[&](Pt from,int j){if(!choices[j].available)return geo::dist(from,nodes[j]);double best=1e100;for(auto d:choices[j].alternatives)best=std::min(best,geo::dist(from,d.point)+std::max(0.,5*d.value-geo::dist(pos,d.point)));return best;};for(int j=0;j<n;++j){task.start[j]=cost(pos,j);for(int i=0;i<n;++i)if(i!=j)task.edge[i][j]=cost(nodes[i],j);}}
    if(opt.joint_actions&&opt.start_residual>0)for(int j=0;j<n;++j)if(kind[j]>0&&choices[j].available)task.start[j]+=opt.start_residual*std::max(0.,choices[j].value*5-geo::dist(pos,nodes[j]));
    if(opt.immediate_fee_weight>0)for(int j=0;j<n;++j){double fee=kind[j]<0?scan_fee():(choices[j].available&&choices[j].measure?5+(channel!=kind[j]):4);task.start[j]+=5*opt.immediate_fee_weight*fee;}
    if(opt.discovery_weight>0){int left=0;for(int k:kind)left+=k<0;double missing=std::max(0,std::min(16-known(),std::max(1,13-known())));for(int j=0;j<n;++j)if(kind[j]<0){double reward=opt.discovery_weight*missing*unseen.probability(nodes[j])*2.5*left;task.start[j]=std::max(0.,task.start[j]-5*reward);}}
    auto solution=opt.use_lns?new_route::solve(task):cert_route::solve(task);order=solution.path;++plans;if(solution.exact)++exact_plans;if(solution.local_optimal)++local_plans;else ++nonlocal_plans;
    double gap=std::max(0.,solution.upper-solution.lower);total_route_gap+=gap;max_route_gap=std::max(max_route_gap,gap);total_route_upper+=solution.upper;max_relative_gap=std::max(max_relative_gap,solution.upper>0?gap/solution.upper:0.);
   }else order=route::optimize(pos,nodes);
   int chosen=order[0],act=kind[chosen];if(opt.joint_actions)++joint_steps;
   if(act<0){int i=-1-act;visited[i]=true;scan(points[i]);}
   else{
    if(opt.joint_actions){io.phase(1);auto d=choices[chosen];if(d.available&&t[act].dynamic_used<opt.dynamic_limit){++t[act].dynamic_used;++dynamic_actions;if(d.measure)measure(d.point,act);else clear(d.point,act);if(opt.complete_source&&!t[act].cleared)locate(act);}else{++dynamic_fallbacks;if(opt.direct_optical)optical(act);else locate_baseline(act);}}
    else locate(act);
    if(opt.auxiliary>=2)supplement(pos,act);
   }
  }
 }
 void run(){Poly points=covering_points();std::vector<bool> visited(points.size());
  if(opt.routing==2){joint_run(points);if(cleared==16){certificate="upper_bound_16";return;}certificate=problem==3?"seven_point_per_channel":"convex_mesh_per_channel";return;}
  for(size_t step=0;step<points.size();++step){size_t j=points.size();double best=1e99;
   if(opt.routing==1){Poly nodes;std::vector<int>ids;for(int i=0;i<(int)points.size();++i)if(!visited[i]){nodes.push_back(points[i]);ids.push_back(i);}j=ids[route::optimize(pos,nodes)[0]];}
   else for(size_t i=0;i<points.size();++i)if(!visited[i]){double score=opt.dynamic?geo::dist(pos,points[i]):double(i);if(score<best){best=score;j=i;}}
   visited[j]=true;scan(points[j]);
   while(cleared<16){int kbest=0;best=1e99;Poly nodes;std::vector<int>ids;for(int k=1;k<=20;++k)if(t[k].obs>0&&!t[k].cleared){auto center=geo::mec(t[k].p).c;nodes.push_back(center);ids.push_back(k);double d=opt.dynamic?geo::dist(pos,center):k;if(d<best){best=d;kbest=k;}}if(!kbest)break;if(opt.routing==1)kbest=ids[route::optimize(pos,nodes)[0]];locate(kbest);}
   if(cleared==16){certificate="upper_bound_16";return;}
  }
  for(int k=1;k<=20;++k)if(t[k].obs&&!t[k].cleared)throw std::runtime_error("pending source at exit");
  certificate=problem==3?"seven_point_per_channel":"convex_mesh_per_channel";
 }
};
