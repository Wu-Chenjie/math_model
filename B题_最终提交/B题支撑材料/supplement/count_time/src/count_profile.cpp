#include "../../../src/simulator.hpp"
#include "../../../src/joint_config.hpp"
#include "../../../src/shortcut_sensor.hpp"
#include <array>
#include <chrono>
#include <iostream>
class CountSensor:public Sensor{
 Sim& sim;std::array<bool,21>seen{};
 public:int scans=0,discovery=0,switch_discovery=0,Jsum=0;
 explicit CountSensor(Sim&s):sim(s){}
 void phase(int p)override{if(p==0)++scans;}
 Reading measure(Pt q,int k)override{
  bool unknown=!seen[k];if(unknown){++discovery;switch_discovery+=(sim.channel!=k);}
  auto out=sim.measure(q,k);
  if(unknown&&out.kind>0){seen[k]=true;Jsum+=scans;}
  return out;
 }
 bool clear(Pt q,int k)override{return sim.clear(q,k);}
 void audit(int k,const Poly&p)override{sim.audit(k,p);}
};
int main(int argc,char**argv){
 if(argc!=5)return 2;int problem=atoi(argv[2]),start=atoi(argv[3]),count=atoi(argv[4]);
 if((problem!=3&&problem!=4)||start<1||count<1)return 2;
 std::ofstream f(argv[1]);if(!f)return 3;
 f<<"problem,seed,method,n,directional_n,time_s,avg_s,move_m,measures,switches,miss,scans,discovery_measures,discovery_switches,Jsum,local_measures,local_switches,discovery_same_channel_savings,cpu_s\n";
 for(int seed=start;seed<start+count;++seed){
  auto truth=make_case(problem,seed);int n=truth.size(),nd=0;for(auto j:truth)nd+=j.directional;
  Sim sim(truth,seed,0);CountSensor counted(sim);auto opt=joint_configuration(78,problem);ShortcutSensor sensor(counted,true);Policy policy(sensor,problem,opt);
  auto begin=std::chrono::steady_clock::now();policy.run();double cpu=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  int nominal=problem==3?7:21,m=counted.scans,d=counted.discovery-counted.switch_discovery;
  if(sim.success!=n||counted.discovery!=m*(20-n)+counted.Jsum||d<0||d>m||m>nominal||(n<16&&m!=nominal))return 4;
  int ml=sim.measures-counted.discovery,sl=sim.switches-counted.switch_discovery;
  double exact=sim.length/5+6*(m*(20-n)+counted.Jsum)-d+5*ml+sl+3*sim.miss+5*n;
  if(std::abs(exact-sim.time)>.001)return 5;
  f<<std::setprecision(15)<<problem<<','<<seed<<",78,"<<n<<','<<nd<<','<<sim.time<<','<<sim.time/n<<','<<sim.length<<','<<sim.measures<<','<<sim.switches<<','<<sim.miss<<','<<m<<','<<counted.discovery<<','<<counted.switch_discovery<<','<<counted.Jsum<<','<<ml<<','<<sl<<','<<d<<','<<cpu<<'\n';
  if((seed-start+1)%25==0){f.flush();std::cout<<problem<<' '<<(seed-start+1)<<'\n';}
 }
}
