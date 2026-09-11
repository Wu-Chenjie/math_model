#include "../src/certified_route.hpp"
#include "../src/configurations.hpp"
#include "../src/simulator.hpp"
#include <cassert>
#include <iostream>
#include <numeric>
#include <random>
#include <iomanip>
double exhaustive(const cert_route::Problem& p){
 std::vector<int> v(p.start.size());std::iota(v.begin(),v.end(),0);double best=1e100;
 do{best=std::min(best,cert_route::length(p,v));}while(std::next_permutation(v.begin(),v.end()));return best;
}
double assignment_exhaustive(const cert_route::Problem& p){
 int n=p.start.size()+1;std::vector<int> v(n);std::iota(v.begin(),v.end(),0);double best=1e100;
 do{double cost=0;bool ok=true;for(int i=0;i<n;++i){int j=v[i];if(i==j){ok=false;break;}if(j)cost+=i?p.edge[i-1][j-1]:p.start[j-1];}if(ok)best=std::min(best,cost);}while(std::next_permutation(v.begin(),v.end()));return best;
}
bool permutation(std::vector<int> r,int n){std::sort(r.begin(),r.end());for(int i=0;i<n;++i)if(r[i]!=i)return false;return int(r.size())==n;}
double neighborhood_best(const cert_route::Problem& p,const std::vector<int>& r){
 double best=cert_route::length(p,r);int n=r.size();
 for(int a=0;a<n;++a)for(int b=a+1;b<n;++b){std::vector<int> s(r.begin(),r.begin()+a);for(int k=b;k>=a;--k)s.push_back(r[k]);s.insert(s.end(),r.begin()+b+1,r.end());best=std::min(best,cert_route::length(p,s));}
 for(int a=0;a<n;++a){auto reduced=r;int item=reduced[a];reduced.erase(reduced.begin()+a);for(int b=0;b<n;++b){auto s=reduced;s.insert(s.begin()+b,item);best=std::min(best,cert_route::length(p,s));}}
 return best;
}
struct NearChange:Sensor{geo::Pt truth{5.4,0};int calls=0;Reading measure(geo::Pt p,int)override{++calls;assert(geo::dist(truth,p+geo::Pt{.4,0})<=5+1e-12);return {1,0};}bool clear(geo::Pt p,int)override{++calls;assert(std::abs(geo::dist(truth,p-geo::Pt{.4,0})-5.8)<1e-12);return geo::dist(truth,p-geo::Pt{.4,0})<=20;}};
class TemporalError:public Sensor{
 Sim sim;int turn=0;geo::Pt actual(geo::Pt p){return p+geo::polar(.4,(++turn)*137.507764);}
 public:TemporalError(int p,int seed):sim(make_case(p,seed,seed%2),seed,seed%2?1:2){}
 Reading measure(geo::Pt p,int k)override{return sim.measure(actual(p),k);}bool clear(geo::Pt p,int k)override{return sim.clear(actual(p),k);}void audit(int k,const geo::Poly& p)override{sim.audit(k,p);}bool full()const{return sim.success==sim.total();}
};
int main(){
 std::mt19937_64 rng(4100931);int small=0,assignments=0,large=0,containments=0;
 auto empty=cert_route::solve({});assert(empty.path.empty()&&empty.lower==0&&empty.upper==0&&empty.exact);
 for(int n=1;n<=9;++n)for(int rep=0;rep<(n==9?6:40);++rep){
  cert_route::Problem p;p.start.resize(n);p.edge.assign(n,std::vector<double>(n));for(auto&x:p.start)x=rng()%2000;for(auto&row:p.edge)for(auto&x:row)x=rng()%2000;
  if(rep%4==0){for(auto&x:p.start)x=0;for(int i=0;i<n;++i)for(int j=0;j<n;++j)if((i+j)%3==0)p.edge[i][j]=0;}
  double best=exhaustive(p);auto s=cert_route::solve(p);assert(s.exact&&s.local_optimal&&permutation(s.path,n));assert(s.lower==best&&s.upper==best&&cert_route::length(p,s.path)==best);
  double lb=cert_route::assignment_lower(p),mst=cert_route::mst_lower(p);assert(lb<=best+1e-8&&mst<=best+1e-8);
  if(n<=7&&rep<12){double a=assignment_exhaustive(p);assert(lb<=a+1e-8&&a-lb<1e-5);++assignments;}++small;
 }
 for(int rep=0;rep<70;++rep){
  int n=13+rng()%22;cert_route::Problem p;p.start.resize(n);p.edge.assign(n,std::vector<double>(n));for(auto&x:p.start)x=(rng()%2000000)/100.;for(auto&row:p.edge)for(auto&x:row)x=(rng()%2000000)/100.;
  auto s=cert_route::solve(p);assert(permutation(s.path,n));assert(std::abs(s.upper-cert_route::length(p,s.path))<1e-8&&s.lower<=s.upper+1e-8);if(s.local_optimal)assert(s.upper-neighborhood_best(p,s.path)<=1.01e-7);++large;
 }
 double eta=.4;for(int i=0;i<25000;++i){
  double rr=i%4?5.000001+(rng()%1494999999)/1000000.:1500,angle=(rng()%3600000)/10000.;double sign=i%2?1:-1;
  auto z=geo::polar(i%3?double(rng()%1799000)/1000.:1800.,(rng()%3600000)/10000.);auto actual=z-geo::polar(rr,angle+sign*1.005);auto nominal=actual-geo::polar(eta,(rng()%3600000)/10000.);
  auto poly=position_error::update(geo::outer_disk({0,0},1800),nominal,angle,eta);assert(geo::contains(poly,z));++containments;
 }
 double step=position_error::grid_side(eta);assert(step/std::sqrt(2.)+eta<20);int nx=std::ceil((1500+2*eta)/step),ny=std::ceil((3000*std::sin(1.005*geo::pi/180)+2*eta)/step);assert(nx*ny==110);
 NearChange io;auto o=configuration(3);o.eta=.4;Policy near(io,3,o);near.measure({0,0},1);assert(near.cleared==1&&io.calls==2);
 int temporal=0;for(int p:{3,4})for(int seed=620001;seed<=620010;++seed){TemporalError sim(p,seed);auto opts=configuration(5);opts.eta=.4;Policy bot(sim,p,opts);bot.run();assert(sim.full());++temporal;}
 for(int n=10;n<=12;++n){cert_route::Problem p;p.start.assign(n,1000);p.edge.assign(n,std::vector<double>(n,1000));p.start[0]=0;for(int i=0;i<n-1;++i)p.edge[i][i+1]=1;auto sol=cert_route::solve(p);assert(sol.exact&&sol.upper==n-1);}
 for(int count:{10,16}){std::vector<Jammer> js;for(int ch=1;ch<=count;++ch)js.push_back({ch,{200,0},1000,false,0});Sim sim(js,1,1);Policy bot(sim,3,configuration(5));bot.run();assert(sim.success==count);assert(bot.known()==count);if(count==16){assert(bot.certificate=="upper_bound_16"&&bot.covered_skips>0);}else assert(bot.certificate=="seven_point_per_channel"&&bot.covered_skips==0);}
 std::cout<<"small_route_bruteforce="<<small<<" assignment_bruteforce="<<assignments<<" large_local_checks="<<large<<" geometric_containments="<<containments<<" temporal_position_cases="<<temporal<<" planted_n10_to12=3 known_count_checks=2 fallback_bound="<<nx*ny<<"\n";
}
