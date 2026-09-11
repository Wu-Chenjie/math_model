#pragma once
#include "common.hpp"
namespace mg {
struct PWL{double lo=0,base=0;Vec len,slope;double hi()const{return lo+std::accumulate(len.begin(),len.end(),0.);}double eval(double x)const{double v=base,t=clip(x-lo,0.,hi()-lo);for(size_t i=0;i<len.size()&&t>1e-10;i++){double z=std::min(t,len[i]);v+=z*slope[i];t-=z;}return v;}};
inline PWL pfun(double n,double p,double q){Vec x{-M/ETA,0,ETA*M};double a=q-n,d=a>=0?ETA*a:a/ETA;if(d>x.front()+1e-8&&d<x.back()-1e-8)x.push_back(d);std::sort(x.begin(),x.end());PWL f;f.lo=x.front();auto cost=[&](double y){return 5*p*pos(n-q+std::max(ETA*y,y/ETA));};f.base=cost(f.lo);for(size_t i=1;i<x.size();i++)if(x[i]-x[i-1]>1e-9){f.len.push_back(x[i]-x[i-1]);f.slope.push_back((cost(x[i])-cost(x[i-1]))/(x[i]-x[i-1]));}return f;}
inline PWL reflect(const PWL&f){PWL g;g.lo=-f.hi();g.base=f.eval(f.hi());g.len.assign(f.len.rbegin(),f.len.rend());for(auto it=f.slope.rbegin();it!=f.slope.rend();it++)g.slope.push_back(-*it);return g;}
struct Segment{double len,slope;int which;};
struct Merge{double lo,base;std::vector<Segment>x;double eval(double z)const{double v=base,t=z-lo;for(auto a:x){double u=clip(t,0.,a.len);v+=u*a.slope;t-=u;if(t<1e-10)break;}return v;}double allocation(double z,int which)const{double ans=0,t=z-lo;for(auto a:x){double u=clip(t,0.,a.len);if(a.which==which)ans+=u;t-=u;if(t<1e-10)break;}return ans;}};
inline Merge merge(const PWL&a,const PWL&b){Merge m{a.lo+b.lo,a.base+b.base,{}};size_t i=0,j=0;while(i<a.len.size()||j<b.len.size()){if(j==b.len.size()||(i<a.len.size()&&a.slope[i]<=b.slope[j])){m.x.push_back({a.len[i],a.slope[i],0});i++;}else{m.x.push_back({b.len[j],b.slope[j],1});j++;}}return m;}
inline PWL gridfun(const Vec&y,double dx){PWL f;f.lo=EMIN;f.base=y[0];double last=-1e100;for(size_t i=1;i<y.size();i++){double s=(y[i]-y[i-1])/dx;check(s>=last-1e-5,"nonconvex Bellman grid");s=std::max(s,last);f.len.push_back(dx);f.slope.push_back(s);last=s;}return f;}
struct Markov{const Scenario&a;const Config&c;const Vec&r;int K,G,T;double dx;Terminal terminal;std::vector<int>bins;Vec cut,pc,transition;std::vector<Vec>v;
 Markov(const Scenario&aa,const Config&cc,const Vec&rr,const Terminal&tt):a(aa),c(cc),r(rr),K(c.lower==1?a.S:3),G(c.grid),T(a.T),dx((EMAX-EMIN)/(G-1)),terminal(tt){bins.assign(a.S*T,0);cut.resize(T*2);pc.assign(T*K,0);transition.assign(T*K*K,0);v.assign((T+1)*K,Vec(G));if(c.lower==0){for(int j=0;j<T;j++){Vec x;for(int s=0;s<a.S;s++)x.push_back(a.Z(s,j,0));cut[j*2]=c.corrected?weighted_quantile(x,a.w,1./3):quantile(x,1./3);cut[j*2+1]=c.corrected?weighted_quantile(x,a.w,2./3):quantile(x,2./3);Vec mass(K,0);for(int s=0;s<a.S;s++){int k=bin(j,a.Z(s,j,0));bins[s*T+j]=k;mass[k]+=a.w[s];pc[j*K+k]+=a.w[s]*a.P(s,j);}for(int k=0;k<K;k++)pc[j*K+k]=mass[k]>1e-15?pc[j*K+k]/mass[k]:a.pc[j];}
 for(int j=0;j<T-1;j++){Vec mass(K,0);for(int s=0;s<a.S;s++){int k=bins[s*T+j],l=bins[s*T+j+1];mass[k]+=a.w[s];transition[(j*K+k)*K+l]+=a.w[s]*(c.corrected?c.concentration:a.S);}for(int k=0;k<K;k++)for(int l=0;l<K;l++)transition[(j*K+k)*K+l]=(transition[(j*K+k)*K+l]+1./K)/(mass[k]*(c.corrected?c.concentration:a.S)+1);}}
 for(int k=0;k<K;k++)for(int i=0;i<G;i++){double E=EMIN+dx*i;v[T*K+k][i]=a.end==YEAR?1000*std::abs(E-INITIAL):terminal.eval(E);}
 for(int j=T-1;j>=0;j--)for(int k=0;k<K;k++){
 Vec weights(a.S,0);double sum=0;if(c.lower==0){for(int s=0;s<a.S;s++)if(bins[s*T+j]==k){weights[s]=a.w[s];sum+=weights[s];}if(sum<1e-15){weights=a.w;sum=1;}for(auto&w:weights)w/=sum;}else weights=kernel(j,{a.Z(k,j,0),a.Z(k,j,1),a.Z(k,j,2)});
 if(c.lower==0&&(!c.condition||c.lower==1)){
 Vec y(G,0);for(int l=0;l<K;l++){double pr=j==T-1?double(l==0):transition[(j*K+k)*K+l];for(int g=0;g<G;g++)y[g]+=pr*v[(j+1)*K+l][g];}PWL next=gridfun(y,dx);for(int s=0;s<a.S;s++)if(weights[s]>1e-15){auto m=merge(reflect(pfun(a.N(s,j),pc[j*K+k],r[j])),next);for(int g=0;g<G;g++)v[j*K+k][g]+=weights[s]*m.eval(EMIN+dx*g);}
 }else{
 // Demand is observed before acting. Its conditional price mean and next-state
 // distribution share the same posterior; actual current prices are never used.
 for(int s=0;s<a.S;s++)if(weights[s]>1e-15){auto cp=condition(j,{a.Z(s,j,0),a.Z(s,j,1),a.Z(s,j,2)});auto m=merge(reflect(pfun(a.N(s,j),cp.first,r[j])),cp.second);for(int g=0;g<G;g++)v[j*K+k][g]+=weights[s]*m.eval(EMIN+dx*g);}}
 (void)gridfun(v[j*K+k],dx);
 }}
 int bin(int j,double error)const{return(error>cut[j*2])+(error>cut[j*2+1]);}
 Vec kernel(int j,const std::array<double,3>&z)const{Vec w(a.S);double sum=0;for(int s=0;s<a.S;s++){double ds=sq((a.Z(s,j,0)-z[0])/a.sn)+.5*sq((a.Z(s,j,1)-z[1])/a.sn)+.5*sq((a.Z(s,j,2)-z[2])/a.sn);w[s]=a.w[s]*std::exp(-ds/(2*sq(c.bandwidth)));sum+=w[s];}for(int s=0;s<a.S;s++)w[s]=(1-c.mixture)*(sum>1e-200?w[s]/sum:a.w[s])+c.mixture*a.w[s];return w;}
 std::pair<double,PWL>condition(int j,const std::array<double,3>&z)const{
 auto w=kernel(j,z);Vec probs(K,0),y(G);double price=0;
 for(int s=0;s<a.S;s++){price+=w[s]*a.P(s,j);if(j<T-1)probs[c.lower==1?s:bins[s*T+j+1]]+=w[s];}
 if(j==T-1)probs[0]=1;
 for(int l=0;l<K;l++)for(int g=0;g<G;g++)y[g]+=probs[l]*v[(j+1)*K+l][g];
 return {price,gridfun(y,dx)};
 }
 double action(int j,double net,double E,double ema,double pastprice){Vec y(G,0);double p=0;if(c.lower==0&&!c.condition){int k=bin(j,net-a.center[j]);p=pc[j*K+k];for(int l=0;l<K;l++){double pr=j==T-1?double(l==0):transition[(j*K+k)*K+l];for(int g=0;g<G;g++)y[g]+=pr*v[(j+1)*K+l][g];}}else{auto cp=condition(j,{net-a.center[j],ema,pastprice*a.sn/a.sp});auto m=merge(reflect(pfun(net,cp.first,r[j])),cp.second);return EMIN+m.allocation(E,1);}auto next=gridfun(y,dx);auto m=merge(reflect(pfun(net,p,r[j])),next);return EMIN+m.allocation(E,1);}
};
struct Action{double E,c,b,em,spill,projection;};
inline Action execute(double E,double target,double r,double n,int global){int left=YEAR-1-global;double lo=std::max(EMIN,E-M/ETA),hi=std::min(EMAX,E+ETA*M);lo=std::max(lo,INITIAL-left*ETA*M);hi=std::min(hi,INITIAL+left*M/ETA);double next=clip(target,lo,hi),c=pos(next-E)/ETA,b=ETA*pos(E-next),gap=r+b-c-n;check(std::isfinite(next)&&lo<=hi+1e-8,"execution infeasible");return{next,c,b,pos(-gap),pos(gap),std::abs(next-target)};}
}
