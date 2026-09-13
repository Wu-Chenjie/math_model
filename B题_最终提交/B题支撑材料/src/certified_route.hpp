#pragma once
#include <vector>
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>
namespace cert_route {
struct Problem{std::vector<double>start;std::vector<std::vector<double>>edge;};
struct Solution{std::vector<int>path;double lower=0,upper=0;bool exact=false,local_optimal=false;};
inline double length(const Problem&p,const std::vector<int>&r){if(r.empty())return 0;double c=p.start[r[0]];for(size_t i=1;i<r.size();++i)c+=p.edge[r[i-1]][r[i]];return c;}
inline double mst_lower(const Problem&p){int n=p.start.size();std::vector<double>d(n+1,1e100);std::vector<bool>done(n+1);d[0]=0;double total=0;
 for(int k=0;k<=n;++k){int u=-1;for(int i=0;i<=n;++i)if(!done[i]&&(u<0||d[i]<d[u]))u=i;done[u]=true;total+=d[u];
  for(int j=0;j<=n;++j)if(!done[j]){double w=u==0?p.start[j-1]:j==0?p.start[u-1]:std::min(p.edge[u-1][j-1],p.edge[j-1][u-1]);d[j]=std::min(d[j],w);}}
 return total;
}
inline double assignment_lower(const Problem&p){int n=p.start.size()+1;double inf=1e12;std::vector<double>u(n+1),v(n+1);std::vector<int>match(n+1),way(n+1);
 auto cost=[&](int i,int j){--i;--j;if(i==j)return inf;if(j==0)return 0.;if(i==0)return p.start[j-1];return p.edge[i-1][j-1];};
 for(int i=1;i<=n;++i){match[0]=i;int j0=0;std::vector<double>minv(n+1,inf);std::vector<bool>used(n+1);
  do{used[j0]=true;int i0=match[j0],j1=0;double delta=inf;
   for(int j=1;j<=n;++j)if(!used[j]){double cur=cost(i0,j)-u[i0]-v[j];if(cur<minv[j]){minv[j]=cur;way[j]=j0;}if(minv[j]<delta){delta=minv[j];j1=j;}}
   for(int j=0;j<=n;++j)if(used[j]){u[match[j]]+=delta;v[j]-=delta;}else minv[j]-=delta;j0=j1;
  }while(match[j0]);
  do{int j1=way[j0];match[j0]=match[j1];j0=j1;}while(j0);
 }
 // Return a conservatively adjusted feasible assignment dual, not a cycle
 // cover primal rounded upward. The adjustment exceeds arithmetic residuals.
 double violation=0;for(int i=1;i<=n;++i)for(int j=1;j<=n;++j)violation=std::max(violation,u[i]+v[j]-cost(i,j));
 double dual=0;for(int i=1;i<=n;++i)dual+=u[i]+v[i];return std::max(0.,dual-n*(violation+1e-8));
}
inline std::vector<int> nearest(const Problem&p,int first=-1){int n=p.start.size();std::vector<bool>used(n);std::vector<int>r;
 if(first>=0){r.push_back(first);used[first]=true;}
 while((int)r.size()<n){int j=-1;double best=1e100;for(int k=0;k<n;++k)if(!used[k]){double c=r.empty()?p.start[k]:p.edge[r.back()][k];if(c<best){best=c;j=k;}}r.push_back(j);used[j]=true;}return r;
}
inline bool improve(const Problem&p,std::vector<int>&r,bool relocate){
 for(int round=0;round<100;++round){double best=length(p,r)-1e-7;std::vector<int>choice;int n=r.size();
  for(int i=0;i<n;++i)for(int j=i+1;j<n;++j){auto test=r;std::reverse(test.begin()+i,test.begin()+j+1);double c=length(p,test);if(c<best){best=c;choice=test;}}
  if(relocate)for(int i=0;i<n;++i)for(int j=0;j<n;++j)if(i!=j){auto test=r;int x=test[i];test.erase(test.begin()+i);test.insert(test.begin()+j,x);double c=length(p,test);if(c<best){best=c;choice=test;}}
  if(choice.empty())return true;r=std::move(choice);
 }return false;
}
inline Solution solve(const Problem&p){Solution s;int n=p.start.size();if(!n){s.exact=s.local_optimal=true;return s;}
 if(n<=12){int states=1<<n;std::vector<double>dp(states*n,1e100);std::vector<signed char>parent(states*n,-1);
  for(int j=0;j<n;++j)dp[(1<<j)*n+j]=p.start[j];
  for(int mask=1;mask<states;++mask)for(int j=0;j<n;++j)if(mask&(1<<j)){double c=dp[mask*n+j];for(int k=0;k<n;++k)if(!(mask&(1<<k))){int index=(mask|(1<<k))*n+k;double v=c+p.edge[j][k];if(v<dp[index]){dp[index]=v;parent[index]=j;}}}
  int mask=states-1,last=0;for(int j=1;j<n;++j)if(dp[mask*n+j]<dp[mask*n+last])last=j;s.upper=dp[mask*n+last];
  while(mask){s.path.push_back(last);int prev=parent[mask*n+last];mask^=1<<last;last=prev;}std::reverse(s.path.begin(),s.path.end());s.lower=s.upper;s.exact=s.local_optimal=true;return s;
 }
 s.path=nearest(p);improve(p,s.path,false);s.upper=length(p,s.path);
 for(int first=0;first<n;++first){auto r=nearest(p,first);improve(p,r,false);double c=length(p,r);if(c<s.upper-1e-7){s.upper=c;s.path=r;}}
 s.local_optimal=improve(p,s.path,true);s.upper=length(p,s.path);
 s.lower=std::max(assignment_lower(p),std::max(0.,mst_lower(p)-1e-6));
 if(s.lower>s.upper+1e-5)throw std::runtime_error("route lower bound exceeds feasible route");return s;
}
}
