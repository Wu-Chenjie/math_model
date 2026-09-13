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
#include "residual_cover.hpp"
#include "neighborhood_tour.hpp"
#include "adaptive_optical.hpp"
#include "optical_portfolio.hpp"
#include "../review/certified_layout21_hex.hpp"
#include <array>
#include <stdexcept>
using geo::Pt;using geo::Poly;
struct Reading {int kind=0;double angle=0;}; // no_signal=0, near=1, direction=2
struct Sensor {virtual Reading measure(Pt,int)=0;virtual bool clear(Pt,int)=0;virtual void audit(int,const Poly&){};virtual void phase(int){};virtual ~Sensor()=default;};
#include "rollout_sensor.hpp"
struct Track {Poly p;Pt first;double angle=0;int obs=0;bool cleared=false;std::vector<dynamic_selection::Event>history;int dynamic_used=0,aux_used=0;};
struct Options {double spacing=950,early=35;bool square=false,dynamic=true;int routing=0;double shiftA=0,shiftB=0;bool shifted=false,includeOrigin=true,opportunistic=false;int fixedLayout=0;double secondA=750,secondB=300,eta=0;bool stop_when_found16=false;int route_model=0;bool use_lns=false;int active_mode=0;int dynamic_depth=0,dp_node_limit=6000;bool joint_actions=false;int auxiliary=0,aux_limit=4;double start_residual=0;bool retreat=false,candidate_menu=false,complete_source=false,direct_optical=false,optical_rotate=false;int planning_samples=32;double q3_radius=1200;bool clear_neighborhood=false,defer_single=false,weighted_optical=false;double optical_weight=1,immediate_fee_weight=0,discovery_weight=0;int dynamic_limit=6;bool adaptive_optical=false;int terminal_mode=0;bool variable_optical=false;int optical_search=0;bool budget_aware=false;int refinement=0;int bearing_bin=2;int optical_portfolio=0;bool shortcut=false;int robust_mode=0;bool residual_cover=false,neighborhood_tour=false,residual_opportunistic=false,neighborhood_variable=false;};
class Policy {
 Sensor& io;int problem;Options opt;std::array<Track,21> t;bool auxiliary_busy=false;discovery::Belief unseen;residual_cover::State remaining_cover;
 public:Pt pos;int channel=1,cleared=0,fallbacks=0,plans=0,exact_plans=0,local_plans=0,nonlocal_plans=0,covered_skips=0;double max_route_gap=0,total_route_gap=0,total_route_upper=0,max_relative_gap=0;std::string certificate="incomplete";
 int dynamic_plans=0,dynamic_actions=0,dynamic_fallbacks=0,dp_expanded=0,dp_budget_hits=0;
 int auxiliary_calls=0,auxiliary_positive=0,joint_steps=0,residual_calls=0,residual_replaced=0,residual_retired=0,rollout_calls=0,rollout_replaced=0;
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
  if(opt.neighborhood_tour&&opt.eta==0){std::vector<Poly>cells;auto centers=adaptive_optical::cover(a.p,a.first,a.angle,&cells);route=neighborhood_tour::optical(route,centers,cells,pos,dynamic_selection::make_hypotheses(a.p,a.history,problem,63));}
  if(opt.neighborhood_variable&&opt.eta==0){std::vector<Poly>cells;auto centers=adaptive_optical::variable_cover(a.p,a.first,a.angle,&cells);auto h=dynamic_selection::make_hypotheses(a.p,a.history,problem,63);auto order=optical_order::choose(centers,pos,h);auto candidate=neighborhood_tour::optical(order,centers,cells,pos,h);
   double oldcost=neighborhood_tour::expected(route,pos,h),newcost=neighborhood_tour::expected(candidate,pos,h);
   if(newcost+5<oldcost&&newcost<.95*oldcost&&neighborhood_tour::length(candidate,pos)<neighborhood_tour::length(route,pos))route=candidate;
  }
  for(auto p:route)if(clear(p,k))return;
  throw std::runtime_error("continuous optical coverage exhausted without success");
 }
 dynamic_selection::Choice rollout_choice(int k,dynamic_selection::Choice base){
  auto &a=t[k];if(!base.available||geo::mec(a.p).r<=35)return base;
  std::vector<dynamic_selection::Alternative>candidate{{base.point,base.measure,base.value}};
  auto fresh=robust_geometry::candidate(a.p,pos,a.first,a.angle,a.history,problem,1);
  if(fresh.valid){double oldrho=base.measure&&robust_geometry::reception(a.p,base.point,a.history,problem)?robust_geometry::worst_radius(a.p,base.point,128).upper:geo::mec(a.p).r;
   double extra=std::max(0.,geo::dist(pos,fresh.q)-geo::dist(pos,base.point))/5+5;
   if(.4*(oldrho-fresh.rho)>extra&&fresh.rho<geo::mec(a.p).r*.85)candidate.push_back({fresh.q,true,0});
  }
  if(candidate.size()==1)return base;
  auto h=dynamic_selection::make_hypotheses(a.p,a.history,problem,4);
  // Include polygon boundary extrema, not just interior particles, for Q3.
  if(problem==3){auto far=a.p.front();for(auto z:a.p)if(geo::dist(z,a.first)>geo::dist(far,a.first))far=z;
   for(auto z:{a.p.front(),far}){dynamic_selection::Hypothesis x{z,1500,false,0,1};if(dynamic_selection::consistent(x,a.history))h.push_back(x);}}
  if(h.empty())return base;
  std::vector<std::vector<double>>costs(candidate.size());
  for(size_t j=0;j<candidate.size();++j)for(auto source:h)for(double error:{-1.,1.}){
   RolloutSensor sensor(source,pos,channel,error,a.history);Options continuation=opt;continuation.robust_mode=0;continuation.residual_cover=false;continuation.neighborhood_tour=false;continuation.auxiliary=0;
   Policy shadow(sensor,problem,continuation);shadow.pos=pos;shadow.channel=channel;shadow.t[k]=a;
   auto d=candidate[j];++shadow.t[k].dynamic_used;
   try{if(d.measure)shadow.measure(d.point,k);else shadow.clear(d.point,k);if(!shadow.t[k].cleared)shadow.locate(k);if(!sensor.cleared)throw std::runtime_error("rollout incomplete");costs[j].push_back(sensor.time);}
   catch(const std::exception&){costs[j].push_back(INFINITY);}++rollout_calls;
  }
  auto mean=[](const std::vector<double>&v){double s=0;for(auto x:v)s+=x;return s/v.size();};
  double best=mean(costs[0]);int selected=0;
  for(size_t j=1;j<candidate.size();++j){double value=mean(costs[j]);double worst_regret=-INFINITY;for(size_t i=0;i<costs[j].size();++i)worst_regret=std::max(worst_regret,costs[j][i]-costs[0][i]);
   if(value+5<best&&worst_regret<=5){best=value;selected=j;}}
  if(selected){++rollout_replaced;base.point=candidate[selected].point;base.measure=candidate[selected].measure;base.value=best;base.alternatives={{base.point,base.measure,best}};}
  return base;
 }
 void locate(int k){io.phase(1);auto &a=t[k];if(a.cleared)return;
  if(opt.dynamic_depth>0&&opt.eta==0){
   for(int step=a.dynamic_used;step<opt.dynamic_limit&&!a.cleared;++step){
    int depth=opt.budget_aware?dynamic_selection::remaining_depth(opt.dynamic_depth,opt.dynamic_limit,a.dynamic_used):opt.dynamic_depth;
    auto decision=dynamic_selection::plan(a.p,pos,a.first,a.angle,a.history,problem,depth,channel==k,opt.dp_node_limit,opt.retreat,opt.planning_samples,opt.clear_neighborhood,opt.terminal_mode,opt.refinement,opt.bearing_bin,opt.robust_mode==3?0:opt.robust_mode);
    if(opt.robust_mode==3)decision=rollout_choice(k,decision);
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
 void joint_run(const Poly&initial_points){Poly points=initial_points;std::vector<bool>visited(points.size());
  while(cleared<16){
   if(opt.residual_opportunistic&&opt.eta==0){bool scanned_before=false;for(auto q:remaining_cover.past)if(geo::dist(q,pos)<1)scanned_before=true;
    if(!scanned_before)for(int i=0;i<(int)points.size();++i)if(!visited[i]&&geo::dist(pos,points[i])>1){
     if(remaining_cover.verify(remaining_cover.sites(points,visited,i,pos,true),true)){visited[i]=true;scan(pos);remaining_cover.scanned(pos);++remaining_cover.retired;remaining_cover.retire(points,visited);residual_retired=remaining_cover.retired;break;}
    }
   }
   Poly nodes;std::vector<int> kind;std::vector<dynamic_selection::Choice>choices;
   bool complete_discovery=opt.stop_when_found16&&known()==16;
   for(int i=0;i<(int)points.size();++i)if(!visited[i]){if(complete_discovery){visited[i]=true;++covered_skips;}else{nodes.push_back(points[i]);kind.push_back(-1-i);choices.push_back({});}}
   bool coverage_left=!nodes.empty();
   for(int k=1;k<=20;++k)if(t[k].obs&&!t[k].cleared){
    if(opt.defer_single&&coverage_left&&t[k].obs==1)continue;
    dynamic_selection::Choice decision;auto &a=t[k];
    if(opt.joint_actions&&opt.dynamic_depth>0&&opt.eta==0&&a.dynamic_used<opt.dynamic_limit){
     int depth=opt.budget_aware?dynamic_selection::remaining_depth(opt.dynamic_depth,opt.dynamic_limit,a.dynamic_used):opt.dynamic_depth;
     decision=dynamic_selection::plan(a.p,pos,a.first,a.angle,a.history,problem,depth,channel==k,opt.dp_node_limit,opt.retreat,opt.planning_samples,opt.clear_neighborhood,opt.terminal_mode,opt.refinement,opt.bearing_bin,opt.robust_mode==3?0:opt.robust_mode);
     if(opt.robust_mode==3)decision=rollout_choice(k,decision);
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
   if(opt.neighborhood_tour&&opt.eta==0){Poly path;std::vector<Poly>cells;bool any=false;
    for(int j:order){path.push_back(nodes[j]);if(kind[j]>0&&geo::mec(t[kind[j]].p).r<20-1e-4){cells.push_back(t[kind[j]].p);path.back()=geo::mec(cells.back()).c;any=true;}else cells.push_back({});}
    if(any){auto moved=neighborhood_tour::optimize(path,cells,pos);for(size_t jj=0;jj<order.size();++jj)if(!cells[jj].empty()){int j=order[jj];nodes[j]=moved[jj];choices[j].available=true;choices[j].measure=false;choices[j].point=moved[jj];}}
   }
   int chosen=order[0],act=kind[chosen];if(opt.joint_actions)++joint_steps;
   if(act<0){int i=-1-act;
    if(opt.residual_cover&&opt.eta==0){points[i]=remaining_cover.replace(points,visited,i,pos);}
    visited[i]=true;scan(points[i]);
    if(opt.residual_cover&&opt.eta==0){remaining_cover.scanned(points[i]);remaining_cover.retire(points,visited);residual_calls=remaining_cover.calls;residual_replaced=remaining_cover.accepted;residual_retired=remaining_cover.retired;}
   }
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
