#include "simulator.hpp"
#include "configurations.hpp"
#include <iostream>
class Hardware:public Sensor{Sim sim;double eta;int seed,mode;
 Pt actual(Pt p){if(mode==0)return p+Pt{eta,0};if(mode==1)return p-Pt{eta,0};if(mode==2)return p+(geo::norm(p)>1e-12?p/geo::norm(p):Pt{1,0})*(-eta);
  uint64_t key=mix((uint64_t)llround(p.x*100))^mix((uint64_t)llround(p.y*100))^mix(seed);return p+geo::polar(eta,360.*(mix(key)>>11)*0x1.0p-53);}
 public:Hardware(std::vector<Jammer>j,int sd,int md):sim(j,sd,md%2?2:1),eta(.4),seed(sd),mode(md){}
 Reading measure(Pt p,int k)override{return sim.measure(actual(p),k);}bool clear(Pt p,int k)override{return sim.clear(actual(p),k);}void audit(int k,const Poly&p)override{sim.audit(k,p);}int total(){return sim.total();}int cleared(){return sim.success;}double time(){return sim.time;}
};
int main(int argc,char**argv){std::ofstream f(argc>1?argv[1]:"hardware.csv");f<<"problem,seed,disturbance,aware,total,cleared,time_s,status,reason\n";int pass=0,unchecked=0;
 for(int p:{3,4})for(int seed=610001;seed<610021;++seed)for(int mode=0;mode<4;++mode)for(int aware=0;aware<2;++aware){auto js=make_case(p,seed,(seed%2)?1:0);Hardware sim(js,seed,mode);Options o=configuration(5);o.eta=aware?.4:0;Policy bot(sim,p,o);std::string status="ok",reason="";try{bot.run();}catch(const std::exception&e){status="diagnostic_interruption";reason=e.what();}
  bool complete=sim.cleared()==sim.total()&&status=="ok";if(aware&&!complete){std::cerr<<"Robust mode failed "<<p<<" "<<seed<<" "<<mode<<"\n";return 1;}if(aware)++pass;else if(!complete)++unchecked;
  f<<std::setprecision(13)<<p<<","<<seed<<","<<mode<<","<<aware<<","<<sim.total()<<","<<sim.cleared()<<","<<sim.time()<<","<<status<<","<<reason<<"\n";
 }
 std::cout<<"Robust runs passed="<<pass<<"; nominal belief checks interrupted="<<unchecked<<"\n";
}
