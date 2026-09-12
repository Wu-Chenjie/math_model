// Independent continuous-angle branch-and-bound audit. Angles in degrees.
// Analytic enclosures; long-double arithmetic with an engineering guard, NOT
// directed-rounding interval arithmetic. See q2_连续审查.md for claim limits.
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <queue>
#include <vector>
using D=long double;
const D PI=acosl(-1.L), EPS=1.005L, GUARD=1e-6L;
struct P {D x=0,y=0;P operator+(P b)const{return{x+b.x,y+b.y};}P operator-(P b)const{return{x-b.x,y-b.y};}P operator*(D t)const{return{x*t,y*t};}};
using Poly=std::vector<P>;
D dot(P a,P b){return a.x*b.x+a.y*b.y;} D cross(P a,P b){return a.x*b.y-a.y*b.x;}
D norm(P a){return hypotl(a.x,a.y);} D dist(P a,P b){return norm(a-b);}
P polar(D r,D a){a*=PI/180;return{r*cosl(a),r*sinl(a)};}
Poly clip(Poly p,P a,D b){Poly v;if(p.empty())return v;for(size_t i=0;i<p.size();++i){P x=p[i],y=p[(i+1)%p.size()];D f=dot(a,x)-b,g=dot(a,y)-b;bool ix=f<=0,iy=g<=0;if(ix)v.push_back(x);if(ix!=iy)v.push_back(x+(y-x)*(f/(f-g)));}return v;}
Poly wedge(Poly p,P q,D a,D e){P u=polar(1,a),v={-u.y,u.x};D t=tanl(e*PI/180);for(P n:{v-u*t,v*(-1)-u*t})p=clip(p,n,dot(n,q));return p;}
Poly sector(bool outer,int n){Poly p={{0,0}};D e=EPS-(outer?0:1e-10L),r=1500+(outer?0:-1e-7L),h=2*e/n;p.push_back(polar(r,-e));if(outer){for(int i=0;i<n;++i)p.push_back(polar(r/cosl(h*PI/360),-e+(i+.5L)*h));p.push_back(polar(r,e));}else for(int i=1;i<=n;++i)p.push_back(polar(r,-e+i*h));return p;}
struct Circle{P c;D r=-1;};
bool inside(Circle c,P p){return c.r>=0&&dist(c.c,p)<=c.r+1e-14L;}
Circle pairc(P a,P b){return{(a+b)*.5L,dist(a,b)*.5L};}
Circle triple(P a,P b,P c){P u=b-a,v=c-a;D den=2*cross(u,v);if(fabsl(den)<1e-20L){Circle z{{},1e30L};for(Circle t:{pairc(a,b),pairc(a,c),pairc(b,c)})if(inside(t,a)&&inside(t,b)&&inside(t,c)&&t.r<z.r)z=t;return z;}D uu=dot(u,u),vv=dot(v,v);P o=a+P{(uu*v.y-vv*u.y)/den,(u.x*vv-v.x*uu)/den};return{o,dist(o,a)};}
Circle mec(const Poly&p){Circle c;for(size_t i=0;i<p.size();++i)if(!inside(c,p[i])){c={p[i],0};for(size_t j=0;j<i;++j)if(!inside(c,p[j])){c=pairc(p[i],p[j]);for(size_t k=0;k<j;++k)if(!inside(c,p[k]))c=triple(p[i],p[j],p[k]);}}for(P z:p)c.r=std::max(c.r,dist(c.c,z));return c;}
struct Witness{D lb=0,theta=0;P z1,z2;};
Witness lower(const Poly&pin,P q,D a,D e=EPS){auto p=wedge(pin,q,a,e-1e-10L);Witness w;w.theta=a;for(P x:p)if(norm(x)>5+GUARD)for(P y:p)if(norm(y)>5+GUARD){D v=dist(x,y)/2-GUARD;if(v>w.lb){w.lb=v;w.z1=x;w.z2=y;}}return w;}
struct Node{D lo,hi,ub;bool operator<(const Node&b)const{return ub<b.ub;}};
struct Result{D lb,ub,qlb,qub;long long nodes;Witness continuous,quantized;};
Result solve(P q,D tol,int n){Poly po=sector(true,n),pi=sector(false,n);D base=atan2l(-q.y,-q.x)*180/PI,lo=1e9,hi=-1e9;P u=polar(1,base);for(P z:po){P d=z-q;D a=atan2l(cross(u,d),dot(u,d))*180/PI;lo=std::min(lo,a);hi=std::max(hi,a);}lo+=base-EPS;hi+=base+EPS;
 std::priority_queue<Node> pq;Witness best,qbest;long long nodes=0;
 auto update=[&](D a){auto w=lower(pi,q,a);if(w.lb>best.lb)best=w;D qa=roundl(a*100)/100;auto qw=lower(pi,q,qa);if(qw.lb>qbest.lb)qbest=qw;};
 auto add=[&](D a,D b){D m=(a+b)/2;D ub=std::max(0.L,mec(wedge(po,q,m,EPS+(b-a)/2)).r)+GUARD;pq.push({a,b,ub});update(m);++nodes;};
 int chunks=std::max(1,(int)ceill((hi-lo)/30));for(int i=0;i<chunks;++i)add(lo+(hi-lo)*i/chunks,lo+(hi-lo)*(i+1)/chunks);update(lo);update(hi);
 while(pq.top().ub-best.lb>tol&&nodes<2000000){Node z=pq.top();pq.pop();D m=(z.lo+z.hi)/2;add(z.lo,m);add(m,z.hi);}
 D ub=pq.top().ub;
 // Exact enumeration of all 0.01-degree readouts in the overcovering interval.
 // Posterior regions use the closed 1.005-degree engineering envelope.
 D qub=0;for(int k=(int)floorl(lo*100);k<=(int)ceill(hi*100);++k){D a=k/100.L;auto w=lower(pi,q,a);if(w.lb>qbest.lb)qbest=w;auto op=wedge(po,q,a,EPS);qub=std::max(qub,std::max(0.L,mec(op).r)+GUARD);}
 return {best.lb,ub,qbest.lb,qub,nodes,best,qbest};
}
int main(int argc,char**argv){D tol=argc>2?strtold(argv[2],nullptr):.05L;int n=argc>3?atoi(argv[3]):64;std::ofstream f(argc>1?argv[1]:"q2_continuous_review.csv");f<<std::setprecision(12)<<"a,b,continuous_lower_m,continuous_upper_m,gap_m,quantized_lower_m,quantized_upper_m,quantized_gap_m,nodes,theta_deg,z1x,z1y,z2x,z2y\n";
 std::vector<P> qs={{650,300},{750,300},{750,400},{850,400}};if(argc>5)qs={{strtold(argv[4],nullptr),strtold(argv[5],nullptr)}};
 for(P q:qs){Result r=solve(q,tol,n);f<<q.x<<','<<q.y<<','<<r.lb<<','<<r.ub<<','<<r.ub-r.lb<<','<<r.qlb<<','<<r.qub<<','<<r.qub-r.qlb<<','<<r.nodes<<','<<r.continuous.theta<<','<<r.continuous.z1.x<<','<<r.continuous.z1.y<<','<<r.continuous.z2.x<<','<<r.continuous.z2.y<<'\n';std::cout<<std::setprecision(12)<<"q="<<q.x<<","<<q.y<<" continuous=["<<r.lb<<","<<r.ub<<"] quantized=["<<r.qlb<<","<<r.qub<<"] nodes="<<r.nodes<<std::endl;if(r.ub+GUARD<r.lb||r.qub+GUARD<r.qlb)return 2;}
}
