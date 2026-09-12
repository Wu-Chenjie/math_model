// Bounded deterministic numeric exploration only; sampling is NOT a certificate.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <vector>
const double PI=acos(-1.0);
struct P{double x,y;};
P polar(double r,double a){return{r*cos(a),r*sin(a)};}
using V=std::vector<P>;
V grid(int nt,bool fine){V g={{0,0}};std::vector<double> rs=fine?std::vector<double>{150,300,450,600,750,850,925,975,1025,1075,1125,1200,1300,1400,1500,1600,1700,1750,1800}:std::vector<double>{350,700,900,1025,1125,1300,1500,1700,1800};for(double r:rs)for(int j=0;j<nt;++j)g.push_back(polar(r,2*PI*(j+.137)/nt));return g;}
double required(P z,const V&p){struct D{double d,a;};D ds[24];int n=p.size();for(int i=0;i<n;++i){double x=p[i].x-z.x,y=p[i].y-z.y;ds[i]={x*x+y*y,atan2(y,x)};if(ds[i].d<1e-15)return 0;}
 std::sort(ds,ds+n,[](D a,D b){return a.d<b.d;});double a[24];int k=0;for(int i=0;i<n;++i){int j=k;while(j>0&&a[j-1]>ds[i].a){a[j]=a[j-1];--j;}a[j]=ds[i].a;++k;if(k<3)continue;double gap=a[0]+2*PI-a[k-1];for(int t=1;t<k;++t)gap=std::max(gap,a[t]-a[t-1]);if(gap<PI-1e-8)return sqrt(ds[i].d);}return 2500;}
double score(const V&p,const V&g){double worst=0,extra=0;for(P z:g){double r=required(z,p);worst=std::max(worst,r);extra+=std::max(0.,r-1000.);}return worst+.15*extra/g.size();}
void save(const V&p,const std::string&fn){std::ofstream f(fn);f<<std::setprecision(12)<<"{\"points\":[";for(size_t i=0;i<p.size();++i)f<<(i?",":"")<<"["<<p[i].x<<","<<p[i].y<<"]";f<<"]}\n";}
int main(int argc,char**argv){std::string dir=argc>1?argv[1]:".";double budget=argc>2?atof(argv[2]):105;auto start=std::chrono::steady_clock::now();auto elapsed=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};std::mt19937_64 rng(2026091104);std::normal_distribution<double> normal(0,1);std::uniform_real_distribution<double> unif(0,1);V g=grid(48,false),dense=grid(720,true);std::ofstream log(dir+"/variable_layout_search.csv");log<<"n,outer,evals,coarse_score,dense_required_radius,seconds\n";
 for(int total:{20,19,18})for(int no:{11,12,10}){int ni=total-no-1;V p={{0,0}};for(int j=0;j<ni;++j)p.push_back(polar(990,2*PI*j/ni+PI/no));for(int j=0;j<no;++j)p.push_back(polar(1945,2*PI*j/no));double cur=score(p,g),best=cur;V bp=p;long long evals=1;double stop=std::min(budget,elapsed()+budget/9);while(elapsed()<stop){V q=p;double progress=1-(stop-elapsed())/(budget/9);double scale=std::max(.25,1-progress);int kind=rng()%10;if(kind<8){int i=1+rng()%(total-1);double r=hypot(q[i].x,q[i].y),a=atan2(q[i].y,q[i].x);r+=normal(rng)*18*scale;a+=normal(rng)*.012*scale;r=std::clamp(r,i<=ni?700.:1850.,i<=ni?1150.:2100.);q[i]=polar(r,a);}else{bool inner=kind==8;double dr=normal(rng)*8*scale,da=normal(rng)*.004*scale;for(int i=1;i<total;++i)if((i<=ni)==inner){double r=hypot(q[i].x,q[i].y)+dr,a=atan2(q[i].y,q[i].x)+da;q[i]=polar(r,a);}}
 double v=score(q,g);++evals;double temp=std::max(.1,2*scale);if(v<cur||unif(rng)<exp((cur-v)/temp)){p=q;cur=v;}if(v<best){best=v;bp=q;}if(evals%400==0){p=bp;cur=best;}}
 double worst=0;for(P z:dense)worst=std::max(worst,required(z,bp));save(bp,dir+"/candidate"+std::to_string(total)+"_outer"+std::to_string(no)+".json");log<<std::setprecision(12)<<total<<","<<no<<","<<evals<<","<<best<<","<<worst<<","<<elapsed()<<"\n";log.flush();std::cout<<"n="<<total<<" outer="<<no<<" evals="<<evals<<" coarse="<<best<<" dense="<<worst<<" elapsed="<<elapsed()<<std::endl;}
 return 0;
}
