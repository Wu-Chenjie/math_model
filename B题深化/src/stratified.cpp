#include "simulator.hpp"
#include "configurations.hpp"
#include <chrono>
#include <iostream>
struct Meta{int n,nd,nb,geom,radius,error,outward,seed;double eig;};
std::vector<Jammer> controlled(int problem,int n,int direction,int boundary,int geom,int rep,int seed,Meta&meta){
 std::mt19937_64 rng(seed);auto U=[&](){return std::generate_canonical<double,53>(rng);};
 auto normal=[&](){return sqrt(-2*log(std::max(U(),1e-12)))*cos(2*geo::pi*U());};
 int nd=problem==3?0:std::clamp((int)round(n*(direction==0?.2:direction==1?.5:.8)),1,n-1);
 int nb=(int)round(n*.5*boundary),radius=1000+250*(rep%3),err=rep%5,ow=rep%2;
 std::vector<int>channels;for(int i=1;i<=20;++i)channels.push_back(i);std::shuffle(channels.begin(),channels.end(),rng);
 std::vector<int>order;for(int i=0;i<n;++i)order.push_back(i);std::shuffle(order.begin(),order.end(),rng);
 std::vector<bool>dir(n);for(int k=0;k<nd;++k)dir[order[k]]=true;
 double base=360*U();std::vector<Jammer>j;double sx=0,sy=0,sxx=0,syy=0,sxy=0;
 for(int k=0;k<n;++k){bool bd=k<nb;double r=bd?1650+150*U():1600*sqrt(U()),theta=360*U();
  if(geom==1)theta=base+(U()<.5?0:180)+.5*normal();
  if(geom==2){theta=base+5*normal();if(!bd)r=std::clamp(700+100*normal(),100.,1400.);}
  Pt p=geo::polar(r,theta);double hd=ow?theta:360*U();j.push_back({channels[k],p,double(radius),dir[k],hd});sx+=p.x;sy+=p.y;sxx+=p.x*p.x;syy+=p.y*p.y;sxy+=p.x*p.y;
 }
 double a=sxx/n-sx*sx/n/n,b=syy/n-sy*sy/n/n,c=sxy/n-sx*sy/n/n,tr=a+b,disc=sqrt(std::max(0.,(a-b)*(a-b)+4*c*c));
 meta={n,nd,nb,geom,radius,err,ow,seed,(tr-disc)/std::max(1e-12,tr+disc)};return j;
}
int main(int argc,char**argv){std::ofstream f(argc>1?argv[1]:"stratified.csv");f<<"case_id,problem,seed,n,nd,nb,geometry,radius,error,outward,eigen_ratio,method,cleared,time_s,avg_s,move_m,measures,switches,miss,fallbacks,runtime_s,certificate\n";int id=0,runs=0;
 for(int p:{3,4})for(int n:{10,13,16})for(int di=0;di<(p==3?1:3);++di)for(int bd=0;bd<3;++bd)for(int g=0;g<3;++g)for(int rep=0;rep<30;++rep){
  int seed=210001+id;Meta meta;auto js=controlled(p,n,di,bd,g,rep,seed,meta);
  for(int method=0;method<3;++method){Sim sim(js,seed,meta.error);Policy bot(sim,p,configuration(method));auto start=std::chrono::steady_clock::now();
   try{bot.run();}catch(const std::exception&e){std::cerr<<"FAIL id="<<id<<" method="<<method<<" "<<e.what()<<"\n";return 1;}
   double rt=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
   if(sim.success!=n||std::abs(sim.time-(sim.length/5+sim.switches+5*sim.measures+3*sim.miss+5*sim.success))>.001)return 2;
   f<<std::setprecision(13)<<id<<","<<p<<","<<seed<<","<<n<<","<<meta.nd<<","<<meta.nb<<","<<g<<","<<meta.radius<<","<<meta.error<<","<<meta.outward<<","<<meta.eig<<","<<method<<","<<sim.success<<","<<sim.time<<","<<sim.time/n<<","<<sim.length<<","<<sim.measures<<","<<sim.switches<<","<<sim.miss<<","<<bot.fallbacks<<","<<rt<<","<<bot.certificate<<"\n";++runs;
  }++id;
 }
 std::cout<<"Verified factorial environments="<<id<<" strategy runs="<<runs<<"\n";
}
