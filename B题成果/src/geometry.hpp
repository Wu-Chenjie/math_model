#pragma once
#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <vector>
namespace geo {
constexpr double pi=3.14159265358979323846;
struct Pt {double x=0,y=0; Pt operator+(Pt b)const{return{x+b.x,y+b.y};} Pt operator-(Pt b)const{return{x-b.x,y-b.y};} Pt operator*(double t)const{return{x*t,y*t};} Pt operator/(double t)const{return{x/t,y/t};}};
inline double dot(Pt a,Pt b){return a.x*b.x+a.y*b.y;}
inline double cross(Pt a,Pt b){return a.x*b.y-a.y*b.x;}
inline double norm(Pt a){return std::hypot(a.x,a.y);}
inline double dist(Pt a,Pt b){return norm(a-b);}
inline Pt polar(double r,double deg){double t=deg*pi/180;return{r*cos(t),r*sin(t)};}
using Poly=std::vector<Pt>;
struct HP{Pt a;double b;}; // a dot x <= b
inline Poly hull(Poly p){
 std::sort(p.begin(),p.end(),[](Pt a,Pt b){return a.x!=b.x?a.x<b.x:a.y<b.y;});
 p.erase(std::unique(p.begin(),p.end(),[](Pt a,Pt b){return dist(a,b)<1e-9;}),p.end());
 if(p.size()<3)return p;
 Poly h(2*p.size());int k=0;
 for(auto x:p){while(k>=2&&cross(h[k-1]-h[k-2],x-h[k-1])<=1e-10)--k;h[k++]=x;}
 int t=k+1;for(int i=(int)p.size()-2;i>=0;--i){auto x=p[i];while(k>=t&&cross(h[k-1]-h[k-2],x-h[k-1])<=1e-10)--k;h[k++]=x;}h.resize(k-1);return h;
}
inline Poly clip(const Poly&p,Pt a,double b){
 Poly q;if(p.empty())return q;
 for(size_t i=0;i<p.size();++i){Pt x=p[i],y=p[(i+1)%p.size()];double fx=dot(a,x)-b,fy=dot(a,y)-b;
  bool ix=fx<=1e-9,iy=fy<=1e-9;if(ix)q.push_back(x);
  if(ix!=iy){double t=fx/(fx-fy);q.push_back(x+(y-x)*t);}}
 return q;
}
inline Poly outer_disk(Pt c,double r,int n=64){Poly p;double rr=r/cos(pi/n);for(int i=0;i<n;++i)p.push_back(c+polar(rr,(i+.5)*360/n));return p;}
inline Poly disk_clip(Poly p,Pt c,double r,int n=64){for(int i=0;i<n;++i){Pt a=polar(1,i*360./n);p=clip(p,a,r+dot(a,c));}return p;}
inline Poly observe(Poly p,Pt s,double theta,double eps=1.005){
 Pt u=polar(1,theta),v={-u.y,u.x};double t=tan(eps*pi/180);
 for(Pt a:{v-u*t,v*(-1)-u*t})p=clip(p,a,dot(a,s));
 return p;
}
inline bool contains(const Poly&p,Pt z){if(p.empty())return false;if(p.size()==1)return dist(p[0],z)<1e-7;
 if(p.size()==2)return std::abs(cross(p[1]-p[0],z-p[0]))<1e-6&&dot(z-p[0],z-p[1])<=1e-6;
 for(size_t i=0;i<p.size();++i)if(cross(p[(i+1)%p.size()]-p[i],z-p[i])< -1e-6)return false;
 return true;}
inline double diameter(const Poly&p){double d=0;for(auto a:p)for(auto b:p)d=std::max(d,dist(a,b));return d;}
struct Circle{Pt c;double r=-1;};
inline bool inside(Circle c,Pt p){return c.r>=0&&dist(c.c,p)<=c.r+1e-7;}
inline Circle paircircle(Pt a,Pt b){return{(a+b)/2,dist(a,b)/2};}
inline Circle triplecircle(Pt a,Pt b,Pt c){
 Pt u=b-a,v=c-a;double d=2*cross(u,v);
 if(std::abs(d)<1e-12){Circle best{{},1e100};for(auto q:{paircircle(a,b),paircircle(a,c),paircircle(b,c)})if(inside(q,a)&&inside(q,b)&&inside(q,c)&&q.r<best.r)best=q;return best;}
 double uu=dot(u,u),vv=dot(v,v);Pt o=a+Pt{(uu*v.y-vv*u.y)/d,(u.x*vv-v.x*uu)/d};return{o,dist(o,a)};
}
// Incremental enclosing circle; final radius enlarged to actual max vertex distance.
inline Circle mec(const Poly&p){Circle c;
 for(size_t i=0;i<p.size();++i)if(!inside(c,p[i])){c={p[i],0};for(size_t j=0;j<i;++j)if(!inside(c,p[j])){c=paircircle(p[i],p[j]);for(size_t k=0;k<j;++k)if(!inside(c,p[k]))c=triplecircle(p[i],p[j],p[k]);}}
 for(auto x:p)c.r=std::max(c.r,dist(x,c.c));
 return c;
}
struct HResult{std::string kind;Poly p;};
inline HResult halfplanes(const std::vector<HP>&h){
 auto feasible=[&](Pt x){for(auto q:h)if(dot(q.a,x)>q.b+1e-8)return false;return true;};
 Poly v;bool exists=feasible({0,0});
 for(auto q:h)if(dot(q.a,q.a)>0&&feasible(q.a*(q.b/dot(q.a,q.a))))exists=true;
 for(size_t i=0;i<h.size();++i)for(size_t j=0;j<i;++j){auto a=h[i],b=h[j];double d=cross(a.a,b.a);if(std::abs(d)<1e-12)continue;
 Pt x={(a.b*b.a.y-a.a.y*b.b)/d,(a.a.x*b.b-a.b*b.a.x)/d};if(feasible(x)){v.push_back(x);exists=true;}}
 if(!exists)return{"empty",{}};
 Poly dirs={{1,0},{-1,0},{0,1},{0,-1}};for(auto q:h){dirs.push_back({-q.a.y,q.a.x});dirs.push_back({q.a.y,-q.a.x});}
 for(auto d:dirs)if(norm(d)>1e-12){d=d/norm(d);bool ok=true,uncertain=false;
  for(auto q:h){double v=dot(q.a,d);if(v>1e-10)ok=false;if(v>0)uncertain=true;}
  // A positive violation accepted only by tolerance is not an unboundedness
  // certificate: report uncertainty instead of inventing a recession ray.
  if(ok)return{uncertain?"numerically_uncertain":"unbounded",{}};
 }
 return{"bounded",hull(v)};
}
inline double segment_distance(Pt z,Pt a,Pt b){Pt d=b-a;double t=dot(d,d)>0?dot(z-a,d)/dot(d,d):0;t=std::clamp(t,0.,1.);return dist(z,a+d*t);}
inline bool meets_disk(Poly p,double r){if(contains(hull(p),{0,0}))return true;for(size_t i=0;i<p.size();++i)if(segment_distance({0,0},p[i],p[(i+1)%p.size()])<=r+1e-7)return true;return false;}
inline Poly coverage(int problem,double h=950,bool square=false){
 if(problem==3){Poly p={{0,0}};for(int i=0;i<6;++i)p.push_back(polar(1200,i*60));return p;}
 Poly p={{0,0}};int n=(int)ceil(4000/h)+2;
 auto v=[&](int i,int j){return square?Pt{i*h,j*h}:Pt{h*(i+.5*j),h*sqrt(3.)/2*j};};
 for(int i=-n;i<n;++i)for(int j=-n;j<n;++j){Pt a=v(i,j),b=v(i+1,j),c=v(i,j+1),d=v(i+1,j+1);
  if(square){Poly q={a,b,d,c};if(meets_disk(q,1800))p.insert(p.end(),q.begin(),q.end());}
  else for(auto q:{Poly{a,b,c},Poly{d,c,b}})if(meets_disk(q,1800))p.insert(p.end(),q.begin(),q.end());}
 Poly unique;for(auto x:p){bool duplicate=false;for(auto y:unique)if(dist(x,y)<1e-6)duplicate=true;if(!duplicate)unique.push_back(x);}return unique;
}
}
