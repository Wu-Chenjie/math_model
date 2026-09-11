#pragma once
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
namespace mg {
using Vec=std::vector<double>;namespace fs=std::filesystem;
constexpr double ETA=.9,M=5000./6,EMIN=1200,EMAX=10800,INITIAL=6000;constexpr int DAY=144,YEAR=52560;
inline void check(bool x,const std::string&m){if(!x)throw std::runtime_error(m);}
inline double sq(double x){return x*x;}inline double pos(double x){return std::max(x,0.);}inline double clip(double x,double lo,double hi){return std::max(lo,std::min(hi,x));}
inline double quantile(Vec v,double q){check(!v.empty(),"empty quantile");std::sort(v.begin(),v.end());double t=q*(v.size()-1);int i=t;return v[i]+(t-i)*(v[std::min(i+1,(int)v.size()-1)]-v[i]);}
inline double sec(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
inline std::string date(int d){int ds[]={31,28,31,30,31,30,31,31,30,31,30,31},m=0;while(m<11&&d>=ds[m])d-=ds[m++];std::ostringstream s;s<<"2025-"<<std::setfill('0')<<std::setw(2)<<m+1<<'-'<<std::setw(2)<<d+1;return s.str();}
inline Vec readvec(std::ifstream&f,int n){Vec a(n);f.read((char*)a.data(),8*n);check(bool(f),"truncated binary");return a;}
struct Data{Vec load,pv,price,forecast,dayprice,dayload,daypv;explicit Data(const std::string&p){std::ifstream f(p,std::ios::binary);check(bool(f),"missing input "+p);char magic[8];int32_t d,t,h;f.read(magic,8);f.read((char*)&d,4);f.read((char*)&t,4);f.read((char*)&h,4);check(std::string(magic,8)=="MGRID001"&&d==365&&t==144&&h==24,"input schema");load=readvec(f,YEAR);pv=readvec(f,YEAR);price=readvec(f,YEAR);forecast=readvec(f,365*4*24);dayprice=readvec(f,144);dayload=readvec(f,144);daypv=readvec(f,144);}const Vec&series(int k)const{return k==0?load:k==1?pv:price;}double net(int t)const{return (load[t]-pv[t])/6.;}};
struct Kind{bool official,variable;};inline Kind kind(const std::string&s){if(s=="q2")return{false,false};if(s=="q3")return{true,false};if(s=="q4_2")return{false,true};if(s=="q4_3")return{true,true};throw std::runtime_error("unknown kind");}
struct Config{int corrected=1,condition=0,metric=0,tail=0;double concentration=7;int horizon=2,count=7,predict=0,scenario=0,lower=0,shared=0,grid=321;double bandwidth=1.5,mixture=.25;std::string str()const{std::ostringstream s;s<<horizon<<' '<<count<<' '<<predict<<' '<<scenario<<' '<<lower<<' '<<shared<<' '<<grid<<' '<<std::setprecision(17)<<bandwidth<<' '<<mixture<<' '<<corrected<<' '<<condition<<' '<<metric<<' '<<tail<<' '<<concentration;return s.str();}static Config parse(const std::string&s){Config c;std::istringstream f(s);f>>c.horizon>>c.count>>c.predict>>c.scenario>>c.lower>>c.shared>>c.grid>>c.bandwidth>>c.mixture;bool basic=bool(f);c.corrected=0;if(f>>c.corrected){f>>c.condition>>c.metric>>c.tail>>c.concentration;check(bool(f),"incomplete v2 config");}check(basic&&c.concentration>0&&c.horizon>=1&&c.horizon<=4&&c.count>0&&c.count<=28&&c.grid>=3&&c.bandwidth>0&&c.mixture>=0&&c.mixture<=1,"invalid config");return c;}};
inline double weighted_quantile(const Vec&v,const Vec&w,double q){
 check(v.size()==w.size()&&!v.empty(),"weighted quantile shape");std::vector<int>ids(v.size());std::iota(ids.begin(),ids.end(),0);std::stable_sort(ids.begin(),ids.end(),[&](int a,int b){return v[a]<v[b];});double mass=0;for(int i:ids){mass+=w[i];if(mass+1e-13>=q)return v[i];}return v[ids.back()];}
struct Terminal{Vec x,y;double lambda=0;bool curved()const{return !x.empty();}double eval(double e)const{if(x.empty())return -lambda*e;auto at=std::upper_bound(x.begin(),x.end(),e);int i=std::clamp(int(at-x.begin())-1,0,int(x.size())-2);return y[i]+(y[i+1]-y[i])*(e-x[i])/(x[i+1]-x[i]);}};
struct Forecast{Vec load,pv,p,net;};
struct Scenario{int S=0,T=0,asof=0,end=0,last_mature=0;Vec n,p,w,center,pc,state;std::vector<int>history;double sn=100,sp=.1,transport=0,ess=0;double N(int s,int j)const{return n[s*T+j];}double P(int s,int j)const{return p[s*T+j];}double Z(int s,int j,int k)const{return state[(s*T+j)*3+k];}void states(){center.assign(T,0);pc.assign(T,0);for(int s=0;s<S;s++)for(int j=0;j<T;j++){center[j]+=w[s]*N(s,j);pc[j]+=w[s]*P(s,j);}double vn=0,vp=0;for(int s=0;s<S;s++)for(int j=0;j<T;j++){vn+=w[s]*sq(N(s,j)-center[j])/T;vp+=w[s]*sq(P(s,j)-pc[j])/T;}sn=std::max(10.,std::sqrt(vn));sp=std::max(.01,std::sqrt(vp));state.assign(S*T*3,0);for(int s=0;s<S;s++){double en=0,ep=0;for(int j=0;j<T;j++){double e=N(s,j)-center[j];en=.8*en+.2*e;state[(s*T+j)*3]=e;state[(s*T+j)*3+1]=en;state[(s*T+j)*3+2]=ep*sn/sp;ep=.8*ep+.2*(P(s,j)-pc[j]);}}}};
}
