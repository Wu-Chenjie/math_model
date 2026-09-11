#include "policy.hpp"
#include <iostream>
#include <iomanip>
// Solver receives observations only; no simulator headers or case data are linked.
struct PipeSensor:Sensor {
 Reading measure(Pt p,int k)override{std::cout<<std::setprecision(17)<<"measure "<<k<<" "<<p.x<<" "<<p.y<<std::endl;Reading r;if(!(std::cin>>r.kind>>r.angle))throw std::runtime_error("bridge ended");return r;}
 bool clear(Pt p,int k)override{std::cout<<std::setprecision(17)<<"clear "<<k<<" "<<p.x<<" "<<p.y<<std::endl;int ok;if(!(std::cin>>ok))throw std::runtime_error("bridge ended");return ok==1;}
};
int main(int argc,char**argv){try{int prob=argc>1?atoi(argv[1]):3;Options o;o.spacing=999;o.shifted=true;o.shiftA=1./6;o.shiftB=11./12;o.includeOrigin=false;o.routing=2;o.opportunistic=true;if(argc>2)o.early=atof(argv[2]);PipeSensor s;Policy bot(s,prob,o);bot.run();std::cout<<"exit "<<bot.cleared<<" "<<bot.certificate<<std::endl;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
