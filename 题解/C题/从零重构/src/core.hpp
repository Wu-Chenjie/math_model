#pragma once
#include <algorithm>
#include <array>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
namespace mg {
constexpr int D=365,T=144,K=4;
constexpr double eta=.9, M=5000./6, emin=1200,emax=10800,Cmax=eta*M,Dmax=M/eta;
inline double clip(double x,double a,double b){return std::max(a,std::min(b,x));}
inline double bus(double x){return x>=0?x/eta:eta*x;}
inline std::vector<double> binary(const std::filesystem::path&p,size_t n){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("Missing "+p.string());std::vector<double>x(n);f.read((char*)x.data(),n*sizeof(double));if(!f||f.peek()!=EOF)throw std::runtime_error("Wrong size "+p.string());return x;}
struct Data{
 std::array<std::vector<double>,3>x;std::vector<double>raw,tariff,dayload,daypv;
 explicit Data(const std::string&p){const char*keys[]={"load","pv","price"};for(int j=0;j<3;j++)x[j]=binary(std::filesystem::path(p)/(std::string("data_")+keys[j]+".bin"),D*T);raw=binary(std::filesystem::path(p)/"data_forecast.bin",D*K*24);tariff=binary(std::filesystem::path(p)/"data_day_price.bin",T);dayload=binary(std::filesystem::path(p)/"data_day_load.bin",T);daypv=binary(std::filesystem::path(p)/"data_day_pv.bin",T);}
 double net(int d,int t)const{return (x[0][d*T+t]-x[1][d*T+t])/6;}
 double old(int j,int h,int t,int d,int release)const {if(h<0||h>d||(h==d&&t>=release))throw std::runtime_error("Future actual observation");return x[j][h*T+t];}
};
inline std::vector<double> gauss(std::vector<double>a,std::vector<double>b,int n){for(int k=0;k<n;k++){int r=k;for(int i=k+1;i<n;i++)if(std::abs(a[i*n+k])>std::abs(a[r*n+k]))r=i;if(std::abs(a[r*n+k])<1e-18)throw std::runtime_error("Singular fit");for(int j=k;j<n;j++)std::swap(a[k*n+j],a[r*n+j]);std::swap(b[k],b[r]);for(int i=k+1;i<n;i++){double z=a[i*n+k]/a[k*n+k];for(int j=k;j<n;j++)a[i*n+j]-=z*a[k*n+j];b[i]-=z*b[k];}}std::vector<double>x(n);for(int i=n-1;i>=0;i--){double s=b[i];for(int j=i+1;j<n;j++)s-=a[i*n+j]*x[j];x[i]=s/a[i*n+i];}return x;}
struct Forecast {
 std::array<std::vector<double>,4>v;
 static size_t ix(int d,int k,int t){return (d*K+k)*T+t;}
 double at(int j,int d,int k,int t)const{return v[j][ix(d,k,t)];}
 // Only already-issued vintages can be used, even when their targets are in the future.
 static double vintage(const Data&a,int d,int k,int t,int age){int issue=d*K+k-age;if(issue<0)return NAN;double u=(d*T+t+1-issue*36)/6.;if(u<0||u>24)return NAN;int hd=issue/4,hk=issue%4;double anchor=(hk? a.old(1,hd,hk*36-1,d,k*36):hd?a.old(1,hd-1,143,d,k*36):0.);int h=(int)std::floor(u);double z=u-h;double left=h==0?anchor:a.raw[(hd*K+hk)*24+h-1];if(z<1e-12)return left;double right=a.raw[(hd*K+hk)*24+h];return left*(1-z)+right*z;}
 Forecast(const Data&a,int mode){for(auto&z:v)z.assign(D*K*T,0);int base=(mode>=3?mode-2:mode);
  for(int j=0;j<3;j++)for(int d=0;d<D;d++){
   std::vector<double>f(T);
   if(d==0){for(int t=0;t<T;t++)f[t]=j==0?a.dayload[t]:j==1?a.daypv[t]:a.tariff[t];}
   else if(base==0||d<14){for(int t=0;t<T;t++){if(j!=1)f[t]=a.old(j,std::max(0,d-7),t,d,0);else{int first=std::max(0,d-7);for(int h=first;h<d;h++)f[t]+=a.old(j,h,t,d,0)/(d-first);}}}
   else {int p=j==1?2:8,w=base==1?28:56;std::vector<double>A(p*p),B(p*T);for(int h=std::max(0,d-w);h<d;h++){std::vector<double>z(p);z[0]=1;z[1]=(h-d)/14.;if(p>2&&h%7)z[1+h%7]=1;double wt=std::exp(-(d-h)/28.);for(int i=0;i<p;i++){for(int l=0;l<p;l++)A[i*p+l]+=wt*z[i]*z[l];for(int t=0;t<T;t++)B[i*T+t]+=wt*z[i]*a.old(j,h,t,d,0);}}A[0]+=1e-8;A[p+1]+=base==1?1:2;for(int i=2;i<p;i++)A[i*p+i]+=.05;for(int t=0;t<T;t++){std::vector<double>b(p);for(int i=0;i<p;i++)b[i]=B[i*T+t];auto c=gauss(A,b,p);f[t]=std::max(j==2?.001:0.,c[0]+((p>2&&d%7)?c[1+d%7]:0.));}if(j!=2){auto q=f;for(int t=1;t<T-1;t++)f[t]=.25*q[t-1]+.5*q[t]+.25*q[t+1];}}
   for(int k=0;k<K;k++)for(int t=0;t<T;t++)v[j][ix(d,k,t)]=f[t];
   if(d>=14)for(int k=1;k<K;k++){int start=k*36,first=std::max(7,d-28),n=d-first;std::vector<double>z(n);double zm=0;for(int h=first;h<d;h++){for(int t=start-36;t<start;t++)z[h-first]+=(a.old(j,h,t,d,start)-at(j,h,0,t))/36;zm+=z[h-first]/n;}double var=0,obs=0;for(double zz:z)var+=(zz-zm)*(zz-zm)/n;for(int t=start-36;t<start;t++)obs+=(a.old(j,d,t,d,start)-f[t])/36;for(int t=start;t<T;t++){double em=0,cov=0;for(int h=first;h<d;h++){double e=a.old(j,h,t,d,start)-at(j,h,0,t);em+=e/n;cov+=(z[h-first]-zm)*e/n;}v[j][ix(d,k,t)]=std::max(j==2?.001:0.,f[t]+em+cov/(1.25*var+1e-12)*(obs-zm));}}
  }
  for(int d=0;d<D;d++)for(int k=0;k<K;k++)for(int t=k*36;t<T;t++){
   double latest=vintage(a,d,k,t,0);v[3][ix(d,k,t)]=latest;if(mode<3||d<14)continue;
   std::vector<int>ages;for(int age=0;age<4;age++)if(std::isfinite(vintage(a,d,k,t,age)))ages.push_back(age);int p=(int)ages.size()+1,first=std::max(7,d-28),n=d-first;std::vector<double>errors(n*p),mu(p),C(p*p),now(p);for(int i=0;i<p-1;i++)now[i]=vintage(a,d,k,t,ages[i]);now[p-1]=at(1,d,k,t);
   for(int h=first;h<d;h++)for(int i=0;i<p;i++){double f=i==p-1?at(1,h,k,t):vintage(a,h,k,t,ages[i]);double e=f-a.old(1,h,t,d,k*36);errors[(h-first)*p+i]=e;mu[i]+=e/n;}
   for(int i=0;i<p;i++)for(int j=0;j<p;j++){for(int h=0;h<n;h++)C[i*p+j]+=(errors[h*p+i]-mu[i])*(errors[h*p+j]-mu[j])/n;C[i*p+j]*=i==j?1:.8;if(i==j)C[i*p+j]+=25;}
   auto w=gauss(C,std::vector<double>(p,1),p);double sw=0,pred=0;for(auto&z:w){z=std::max(0.,z);sw+=z;}if(sw<1e-12){w.assign(p,1);sw=p;}for(int i=0;i<p;i++)pred+=w[i]/sw*(now[i]-mu[i]);v[3][ix(d,k,t)]=std::max(0.,pred);
  }
 }
 double net(int d,int k,int t,bool official)const{return (at(0,d,k,t)-at(official?3:1,d,k,t))/6.;}
};
struct Seg{double len,slope;};
struct Pwl{double lo=0,y=0;std::vector<Seg>s;double hi()const{double a=lo;for(auto z:s)a+=z.len;return a;}double eval(double x)const{if(x<lo-1e-5||x>hi()+1e-5)throw std::runtime_error("Value outside PWL domain");double b=y,rem=std::max(0.,x-lo);for(auto z:s){double take=std::min(rem,z.len);b+=take*z.slope;rem-=take;if(rem<1e-9)break;}return b;}};
inline void append(Pwl&v,double len,double slope){if(len<1e-10)return;if(!v.s.empty()&&std::abs(v.s.back().slope-slope)<1e-12)v.s.back().len+=len;else v.s.push_back({len,slope});}
inline Pwl restrict_to(Pwl a,double low,double high){low=std::max(low,a.lo);high=std::min(high,a.hi());if(low>high+1e-6)throw std::runtime_error("Empty PWL domain");Pwl b;b.lo=low;b.y=a.eval(low);double pos=a.lo;for(auto z:a.s){double end=pos+z.len;append(b,std::max(0.,std::min(end,high)-std::max(pos,low)),z.slope);pos=end;}return b;}
inline Pwl merge(const Pwl&a,const Pwl&b){Pwl c;c.lo=a.lo+b.lo;c.y=a.y+b.y;size_t i=0,j=0;while(i<a.s.size()||j<b.s.size()){bool av=j==b.s.size()||(i<a.s.size()&&a.s[i].slope<=b.s[j].slope);auto z=av?a.s[i++]:b.s[j++];append(c,z.len,z.slope);}return c;}
inline double allocate(const Pwl&v,const Pwl&h,double E){double left=clip(E-v.lo-h.lo,0.,v.hi()+h.hi()-v.lo-h.lo),e=v.lo;size_t i=0,j=0;while(left>1e-9&&(i<v.s.size()||j<h.s.size())){bool av=j==h.s.size()||(i<v.s.size()&&v.s[i].slope<=h.s[j].slope);auto z=av?v.s[i++]:h.s[j++];double take=std::min(left,z.len);if(av)e+=take;left-=take;}return clip(e,v.lo,v.hi());}
inline Pwl stage(const std::vector<double>&net,const std::vector<double>&price,const std::vector<double>&w,int N,int t,double q,double penalty){std::vector<double>b{-Dmax,0,Cmax};for(size_t s=0;s<w.size();s++){double bal=q-net[s*N+t],z=bal>=0?eta*bal:bal/eta;if(z>-Dmax&&z<Cmax)b.push_back(z);}std::sort(b.begin(),b.end());b.erase(std::unique(b.begin(),b.end(),[](double a,double c){return std::abs(a-c)<1e-9;}),b.end());Pwl g;g.lo=-Dmax;for(size_t s=0;s<w.size();s++)g.y+=penalty*w[s]*price[s*N+t]*std::max(0.,net[s*N+t]-q+bus(-Dmax));for(size_t k=1;k<b.size();k++){double mid=(b[k]+b[k-1])/2,slope=0;for(size_t s=0;s<w.size();s++)if(net[s*N+t]-q+bus(mid)>0)slope+=penalty*w[s]*price[s*N+t]*(mid>=0?1/eta:eta);append(g,b[k]-b[k-1],slope);}Pwl h;h.lo=-Cmax;h.y=g.eval(Cmax);for(auto it=g.s.rbegin();it!=g.s.rend();++it)append(h,it->len,-it->slope);return h;}
struct DPResult{std::vector<double>e;double value;};
inline DPResult dp(const std::vector<double>&net,const std::vector<double>&p,const std::vector<double>&w,const std::vector<double>&q,double initial,bool closed,double terminal,double lambda,double penalty=5){int N=q.size();std::vector<Pwl>v(N+1),h(N);if(closed){v[N].lo=terminal;v[N].y=0;}else{v[N].lo=emin;v[N].y=-lambda*(emin-6000);v[N].s={{emax-emin,-lambda}};}for(int t=N-1;t>=0;t--){h[t]=stage(net,p,w,N,t,q[t],penalty);v[t]=restrict_to(merge(v[t+1],h[t]),emin,emax);}DPResult r;r.value=v[0].eval(initial);r.e.push_back(initial);for(int t=0;t<N;t++)r.e.push_back(allocate(v[t+1],h[t],r.e.back()));return r;}
struct Config{int model=0,lower=0;double scale=1,gamma=0,lambdaFactor=.9;int iterations=600;};
struct Scenes{int S=0,N=144;std::vector<double>n,p,shift;};
inline Scenes scenarios(const Data&a,const Forecast&f,int d,int release,bool official,bool variable,double scale){Scenes z;int first=std::max(14,d-28);if(first>=d)first=std::max(7,d-7);z.S=d-first;z.N=T-release*36;for(int h=first;h<d;h++)for(int t=release*36;t<T;t++){double center=f.net(d,release,t,official);z.n.push_back(center+scale*(a.net(h,t)-f.net(h,release,t,official)));z.p.push_back(variable?std::max(.001,f.at(2,d,release,t)+a.x[2][h*T+t]-f.at(2,h,release,t)):a.tariff[t]);z.shift.push_back(official?scale*(f.net(h,t/36,t,true)-f.net(h,0,t,true)):0.);}return z;}
struct Act{double next,A,B,G,em,sp,c,d;};
inline Act action(double E,double r,double n,double reserve,int t,bool close){double raw=(r-n)>=0?eta*(r-n):(r-n)/eta;double delta=clip(raw,-Dmax,Cmax),der=(raw>-Dmax&&raw<Cmax)?((r-n)>=0?eta:1/eta):0.;double lo=emin,hi=emax,dl=0,dh=0;if(E-Dmax>lo){lo=E-Dmax;dl=1;}if(E+Cmax<hi){hi=E+Cmax;dh=1;}if(close){double l=6000-(143-t)*Cmax,u=6000+(143-t)*Dmax;if(l>lo){lo=l;dl=0;}if(u<hi){hi=u;dh=0;}}double floor=reserve,df=0,dg=1;if(floor<lo){floor=lo;df=dl;dg=0;}if(floor>hi){floor=hi;df=dh;dg=0;}double next=E+delta,A=1,B=der,G=0;if(next<floor){next=floor;A=df;B=0;G=dg;}if(next>hi){next=hi;A=dh;B=0;G=0;}double dd=next-E,balance=r-n-bus(dd);return {next,A,B,G,std::max(-balance,0.),std::max(balance,0.),std::max(dd,0.)/eta,eta*std::max(-dd,0.)};}
struct Eval{double cost=0;std::vector<double>gq,gr;};
inline Eval loss(const Scenes&z,const std::vector<double>&q,const std::vector<double>&res,double initial,bool closed,double gamma,double lambda,bool grad){Eval out;if(grad){out.gq.assign(T,0);out.gr.assign(24,0);}for(int s=0;s<z.S;s++){double E=initial,cost=0;std::array<Act,T>acts;std::array<double,T>rr,dd,drdq;for(int t=0;t<T;t++){int ix=s*T+t;double raw=q[t]+gamma*z.shift[ix],r=std::max(0.,raw);rr[t]=r;drdq[t]=raw>0?1:0;auto ac=action(E,r,z.n[ix],res[t/6],t,closed);dd[t]=ac.next-E;acts[t]=ac;cost+=z.p[ix]*(q[t]+1.5*std::max(r-q[t],0.)-.5*std::max(q[t]-r,0.)+5*ac.em);E=ac.next;}if(!closed)cost-=lambda*(E-6000);out.cost+=cost/z.S;if(grad){double adj=closed?0:-lambda;for(int t=T-1;t>=0;t--){double p=z.p[s*T+t],em=acts[t].em>1e-9?5*p:0.,deltagrad=em*(dd[t]>=0?1/eta:eta),u=adj+deltagrad;bool up=rr[t]>=q[t];double fq=up?-.5*p:.5*p,fr=up?1.5*p:.5*p;out.gq[t]+=(fq+drdq[t]*(fr-em+u*acts[t].B))/z.S;out.gr[t/6]+=u*acts[t].G/z.S;adj=-deltagrad+u*acts[t].A;}}}return out;}
struct Plan{std::vector<double>q,res;double model_cost=0;};
inline Plan plan(const Data&a,const Forecast&f,int day,bool official,bool variable,const Config&c,double E,bool closed,double lambda){auto z=scenarios(a,f,day,0,official,variable,c.scale);std::vector<double>nom(T),price(T),q(T),res(24,emin);for(int t=0;t<T;t++){nom[t]=f.net(day,0,t,official);price[t]=variable?std::max(.001,f.at(2,day,0,t)):a.tariff[t];}auto seed=dp(nom,price,{1},q,E,true,closed?6000:emin,0,1);for(int t=0;t<T;t++)q[t]=std::max(0.,nom[t]+bus(seed.e[t+1]-seed.e[t]));std::vector<double>m(T+24),v(T+24);Plan best;best.model_cost=1e100;double b1=1,b2=1;for(int it=0;it<c.iterations;it++){auto l=loss(z,q,res,E,closed,c.gamma,lambda,true);if(l.cost<best.model_cost){best.q=q;best.res=res;best.model_cost=l.cost;}b1*=.9;b2*=.999;for(int i=0;i<T+24;i++){double g=i<T?l.gq[i]:l.gr[i-T];m[i]=.9*m[i]+.1*g;v[i]=.999*v[i]+.001*g*g;double lr=(i<T?30:120)/std::sqrt(1+it/150.);double step=lr*(m[i]/(1-b1))/(std::sqrt(v[i]/(1-b2))+1e-8);if(i<T)q[i]=std::max(0.,q[i]-step);else res[i-T]=clip(res[i-T]-step,emin,emax);}}return best;}
inline double mpc_target(const Scenes&z,const std::vector<double>&q,const std::vector<double>&observed,int j,double E,bool close,double lambda){int N=z.N-j,S=z.S;std::vector<double>w(S,0),net(S*N),prices(S*N),qr(q.begin()+j,q.end());int first=std::max(0,j-5);for(int t=first;t<=j;t++){double mean=0,var=0;for(int s=0;s<S;s++)mean+=z.n[s*z.N+t]/S;for(int s=0;s<S;s++)var+=std::pow(z.n[s*z.N+t]-mean,2)/S;double scale=std::max(25.,std::sqrt(var));for(int s=0;s<S;s++)w[s]+=-.5*std::pow((z.n[s*z.N+t]-observed[t])/scale,2)/(j-first+1);}double ma=*std::max_element(w.begin(),w.end()),sum=0;for(double&x:w){x=std::exp(x-ma);sum+=x;}for(double&x:w)x=.8*x/sum+.2/S;for(int s=0;s<S;s++)for(int t=0;t<N;t++){net[s*N+t]=t?z.n[s*z.N+j+t]:observed[j];prices[s*N+t]=z.p[s*z.N+j+t];}return dp(net,prices,w,qr,E,close,6000,lambda).e[1];}
inline std::string date(int d){using namespace std::chrono;year_month_day y{sys_days{year{2025}/January/1}+days{d}};std::ostringstream o;o<<int(y.year())<<'-'<<std::setw(2)<<std::setfill('0')<<unsigned(y.month())<<'-'<<std::setw(2)<<unsigned(y.day());return o.str();}
}
