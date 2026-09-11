#include <algorithm>
#include <cmath>
#include <cstdint>
#include <numeric>
#include <vector>
#include <stdexcept>
// All energy quantities are kWh per 10-minute slot. No fast-math.
// Explicit FMA in interpolation matches the installed NumPy arm64 interp.
namespace {
constexpr double eta=.9, m=5000./6.;
double interp(double x,const double* g,const double* v,int n){
 if(x<=g[0])return v[0]; if(x>=g[n-1])return v[n-1];
 const int k=int(std::upper_bound(g,g+n,x)-g)-1;
 if(x==g[k])return v[k];
 return std::fma((v[k+1]-v[k])/(g[k+1]-g[k]), x-g[k], v[k]);
}
void convolution(const double* g,const double* v,int n,double a,double p,double* out){
 const double lo=-eta*m,hi=m/eta;
 std::vector<double> ys={lo,hi,0.,std::clamp(a/eta,lo,hi),std::clamp(a*eta,lo,hi)};
 std::sort(ys.begin(),ys.end());ys.erase(std::unique(ys.begin(),ys.end()),ys.end());
 std::vector<double> cost(ys.size()),length,slopes;
 for(size_t i=0;i<ys.size();++i)cost[i]=5*p*std::max(0.,a+std::max(-eta*ys[i],-ys[i]/eta));
 for(int i=0;i<n-1;++i){length.push_back(g[i+1]-g[i]);slopes.push_back((v[i+1]-v[i])/length.back());}
 for(size_t i=0;i+1<ys.size();++i){length.push_back(ys[i+1]-ys[i]);slopes.push_back((cost[i+1]-cost[i])/length.back());}
 std::vector<int> order(length.size());std::iota(order.begin(),order.end(),0);
 std::stable_sort(order.begin(),order.end(),[&](int i,int j){return slopes[i]<slopes[j];});
 std::vector<double> knots(order.size()+1),values(order.size()+1);
 knots[0]=g[0]+ys[0];values[0]=v[0]+cost[0];double dx=0,dy=0;
 for(size_t i=0;i<order.size();++i){int k=order[i];dx+=length[k];dy+=length[k]*slopes[k];knots[i+1]=knots[0]+dx;values[i+1]=values[0]+dy;}
 for(int i=0;i<n;++i)out[i]=interp(g[i],knots.data(),values.data(),int(knots.size()));
}
}
extern "C" {
int mg_convolution(const double* g,const double* v,int n,double a,double p,double* out){
 try{if(n<2)return 1;convolution(g,v,n,a,p,out);return 0;}catch(...){return 2;}
}
int mg_markov(const double* net,const double* prices,const double* q,const double* weights,
 const int64_t* labels,const double* grid,const double* terminal,int S,int T,int B,int G,
 int legacy,double* future,double* cond_price,double* initial){
 try{
 if(S<1||T<1||B<1||G<2)return 1;
 std::vector<double> v(B*G),cur(B*G),P(B*B),tmp(G);
 for(int k=0;k<B;++k)std::copy(terminal,terminal+G,v.begin()+k*G);
 for(int j=T-1;j>=0;--j){
  std::fill(P.begin(),P.end(),0.);
  if(j<T-1)for(int s=0;s<S;++s)P[labels[s*T+j]*B+labels[s*T+j+1]]+=legacy?1.:S*weights[s];
  for(int k=0;k<B;++k){double total=0;for(int l=0;l<B;++l)total+=P[k*B+l];for(int l=0;l<B;++l)P[k*B+l]=(P[k*B+l]+1./B)/(total+1.);}
  double* nxt=future+j*B*G;
  for(int k=0;k<B;++k)for(int h=0;h<G;++h){double sum=0;for(int l=0;l<B;++l)sum+=P[k*B+l]*v[l*G+h];nxt[k*G+h]=sum;}
  for(int k=0;k<B;++k){
   std::vector<int> ids;for(int s=0;s<S;++s)if(labels[s*T+j]==k)ids.push_back(s);
   if(ids.empty()){ids.resize(S);std::iota(ids.begin(),ids.end(),0);}
   double mass=0,price=0;for(int s:ids)mass+=weights[s];
   if(legacy){for(int s:ids)price+=prices[s*T+j];price/=ids.size();}
   else for(int s:ids)price+=(weights[s]/mass)*prices[s*T+j];
   cond_price[j*B+k]=price;std::fill(cur.begin()+k*G,cur.begin()+(k+1)*G,0.);
   for(int s:ids){convolution(grid,nxt+k*G,G,net[s*T+j]-q[j],price,tmp.data());
    for(int h=0;h<G;++h)cur[k*G+h]+=legacy?tmp[h]:(weights[s]/mass)*tmp[h];}
   if(legacy)for(int h=0;h<G;++h)cur[k*G+h]/=ids.size();
  }
  v.swap(cur);
 }
 std::copy(v.begin(),v.end(),initial);return 0;
 }catch(...){return 2;}
}
// Fill exact CSR expressions for Q/R/E. No LP inequality or solver changes.
int64_t mg_expression(int which,int S,int T,int F,int64_t asof,int intercept,int gain,
 const double* energy,const double* previous,const double* base,int has_base,
 int64_t* indptr,int64_t* indices,double* values,double* constant){
 int64_t z=0;indptr[0]=0;
 for(int s=0;s<S;++s)for(int j=0;j<T;++j){
  int64_t ts=asof+j,row=int64_t(s)*T+j;int di=int(ts/144-asof/144),bi=int(ts/36-asof/36);
  constant[row]=0.;
  if(which==0&&di==0&&has_base)constant[row]=base[j];
  else{
   indices[z]=intercept+j;values[z++]=1.;
   int reveal=which==0?int(ts/144*144-asof):which==1?int(ts/36*36-asof):j+1;
   if(reveal>0){const double* feature=(which==2?energy+(row*F):previous+(int64_t(s)*T+reveal-1)*F);
    int col=gain+F*(which==0?di:bi);
    for(int k=0;k<F;++k){indices[z]=col+k;values[z++]=feature[k];}
   }
  }
  indptr[row+1]=z;
 }
 return z;
}
}
