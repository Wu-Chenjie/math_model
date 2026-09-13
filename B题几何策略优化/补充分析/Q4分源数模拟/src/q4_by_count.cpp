#include "../../../src/simulator.hpp"
#include "../../../src/joint_config.hpp"
#include "../../../src/shortcut_sensor.hpp"
#include <chrono>
#include <iostream>
#include <stdexcept>
class ScanCount:public Sensor{
 Sensor& io;
 public:int scans=0;
 explicit ScanCount(Sensor& s):io(s){}
 Reading measure(Pt q,int k)override{return io.measure(q,k);}
 bool clear(Pt q,int k)override{return io.clear(q,k);}
 void audit(int k,const Poly&p)override{io.audit(k,p);}
 void phase(int p)override{if(p==0)++scans;io.phase(p);}
};

inline std::vector<Jammer> make_case_fixed(int seed,int n){
 if(n<10||n>16)throw std::invalid_argument("source count out of statement range");
 std::mt19937_64 rng(seed);auto U=[&](){return std::generate_canonical<double,53>(rng);};
 std::vector<int>ch;for(int k=1;k<=20;++k)ch.push_back(k);std::shuffle(ch.begin(),ch.end(),rng);
 int nd=1+int(rng()%(n-1));std::vector<Jammer>j;
 for(int k=0;k<n;++k){Pt p;do{p=geo::polar(1800*sqrt(U()),360*U());}while(std::any_of(j.begin(),j.end(),[&](Jammer a){return geo::dist(a.p,p)<40;}));
  j.push_back({ch[k],p,1000+500*U(),k<nd,360*U()});}
 return j;
}

int main(int argc,char**argv){
 if(argc!=6){std::cerr<<"q4_by_count OUTPUT N START COUNT METHOD\n";return 2;}
 int n=atoi(argv[2]),start=atoi(argv[3]),count=atoi(argv[4]),method=atoi(argv[5]);
 if(n<10||n>16||start<1||count<1||(method!=78&&method!=84))return 2;
 std::ofstream f(argv[1]);if(!f)return 3;
 f<<"problem,seed,method,n,directional_n,cleared,time_s,avg_s,move_m,measures,switches,miss,fallbacks,scans,skipped_discovery,certificate,runtime_s\n";
 for(int i=0;i<count;++i){
  int seed=start+i;auto truth=make_case_fixed(seed,n);
  if((int)truth.size()!=n)return 4;
  int nd=0;for(auto j:truth)nd+=j.directional;
  Sim sim(truth,seed,0);ScanCount counted(sim);auto opt=joint_configuration(method,4);
  ShortcutSensor sensor(counted,opt.shortcut&&opt.eta==0);Policy bot(sensor,4,opt);
  auto begin=std::chrono::steady_clock::now();
  try{bot.run();if(sim.success!=n)throw std::runtime_error("incomplete");
   double cost=sim.length/5+sim.switches+5*sim.measures+3*sim.miss+5*sim.success;
   if(std::abs(sim.time-cost)>.001)throw std::runtime_error("accounting");}
  catch(const std::exception&e){std::cerr<<"FAIL n="<<n<<" seed="<<seed<<" method="<<method<<" "<<e.what()<<"\n";return 1;}
  double cpu=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  if(n<16&&counted.scans!=21){std::cerr<<"FAIL expected 21 discovery stops\n";return 6;}
  f<<std::setprecision(13)<<"4,"<<seed<<","<<method<<","<<n<<","<<nd<<","<<sim.success<<","<<sim.time<<","<<sim.time/n<<","<<sim.length<<","<<sim.measures<<","<<sim.switches<<","<<sim.miss<<","<<bot.fallbacks<<","<<counted.scans<<","<<bot.covered_skips<<","<<bot.certificate<<","<<cpu<<"\n";
  if((i+1)%10==0){f.flush();std::cout<<"n="<<n<<" method="<<method<<" cases="<<i+1<<"\n";}
 }
}
