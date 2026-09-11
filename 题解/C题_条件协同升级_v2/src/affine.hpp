#pragma once
#include "common.hpp"
#include <Highs.h>
namespace mg {
struct SparseLP{HighsLp p;std::vector<HighsInt>start{0},idx;Vec val;void row(std::initializer_list<std::pair<int,double>>x,double rhs){for(auto[i,v]:x)if(std::abs(v)>1e-15){idx.push_back(i);val.push_back(v);}start.push_back(idx.size());p.row_lower_.push_back(-kHighsInf);p.row_upper_.push_back(rhs);}void row(const std::vector<std::pair<int,double>>&x,double rhs){for(auto[i,v]:x)if(std::abs(v)>1e-15){idx.push_back(i);val.push_back(v);}start.push_back(idx.size());p.row_lower_.push_back(-kHighsInf);p.row_upper_.push_back(rhs);}void finish(int n){p.num_col_=n;p.num_row_=p.row_upper_.size();p.a_matrix_.format_=MatrixFormat::kRowwise;p.a_matrix_.start_=std::move(start);p.a_matrix_.index_=std::move(idx);p.a_matrix_.value_=std::move(val);}};
struct Plan{Vec q,r;double objective=0,dual=0,gap=0,residual=0,seconds=0,lambda=0;};
inline Terminal terminal_model(const Data&,int,int,Kind,const Config&,double);
inline Plan affine(const Data&data,const Scenario&a,const Config&cfg,Kind k,double E,const Vec&base){double began=sec();int T=a.T,S=a.S,blocks=(a.end/36)-(a.asof/36);int nq=T,nr=S*T,ne=S*T,nu=S*T,nd=S*T;int Q=0,R=Q+nq,A=R+nr,G=A+T,F=G+blocks*3,U=F+ne,D=U+nu,N=D+nd;bool curved=cfg.tail&&a.end!=YEAR;int W=N;if(curved)N+=S;SparseLP lp;lp.p.col_cost_.assign(N,0);lp.p.col_lower_.assign(N,-kHighsInf);lp.p.col_upper_.assign(N,kHighsInf);for(int j=0;j<T;j++){lp.p.col_lower_[Q+j]=0;if(a.asof%144&&j<144-a.asof%144)lp.p.col_lower_[Q+j]=lp.p.col_upper_[Q+j]=base[j];}for(int i=0;i<nr;i++)lp.p.col_lower_[R+i]=0;for(int i=0;i<ne;i++){lp.p.col_lower_[F+i]=EMIN;lp.p.col_upper_[F+i]=EMAX;lp.p.col_lower_[U+i]=0;lp.p.col_lower_[D+i]=0;}for(int b=0;b<blocks;b++)for(int z=0;z<3;z++){lp.p.col_lower_[G+3*b+z]=-10;lp.p.col_upper_[G+3*b+z]=10;}
 Vec prices=a.pc;int b6=std::min(36,T);double lambda=.9*quantile(Vec(prices.end()-b6,prices.end()),.35)/ETA;
 if(a.end==YEAR)lambda=0;
 for(int s=0;s<S;s++)for(int j=0;j<T;j++){int i=s*T+j,t=a.asof+j,block=j/36;double prob=a.w[s];lp.p.col_cost_[R+i]=prob*a.P(s,j);lp.p.col_cost_[U+i]=prob*5*a.P(s,j);lp.p.col_cost_[D+i]=prob*.5*a.P(s,j);
 if(!k.official||t%144<36){lp.row({{R+i,1},{Q+j,-1}},0);lp.row({{Q+j,1},{R+i,-1}},0);}else{
 int rel=t/36*36;int posrel=rel-a.asof;if(posrel==0){for(int z=0;z<3;z++){lp.p.col_lower_[G+3*block+z]=0;lp.p.col_upper_[G+3*block+z]=0;}lp.row({{R+i,1},{Q+j,-1}},0);lp.row({{Q+j,1},{R+i,-1}},0);}else{
 // Contract revisions are affine only in already observed residual features.
 double z0=0,z1=0,z2=0;int b0=std::max(0,posrel-36);for(int u=b0;u<posrel;u++)z0+=(a.N(s,u)-a.center[u])/(posrel-b0);z1=a.Z(s,posrel-1,1);z2=a.Z(s,posrel-1,2);if(cfg.shared)z0=a.Z(s,posrel-1,0);
 std::vector<std::pair<int,double>> row{{R+i,1},{Q+j,-1},{G+3*block,-z0},{G+3*block+1,-z1},{G+3*block+2,-z2}};lp.row(row,0);for(auto&[id,v]:row)v=-v;lp.row(row,0);
 }}
 lp.row({{R+i,1},{Q+j,-1},{D+i,-1}},0);lp.row({{Q+j,1},{R+i,-1},{D+i,-1}},0);
 // Affine internal energy uses current demand and past prices, never current price.
 std::vector<std::pair<int,double>> eq{{F+i,1},{A+j,-1}};
 for(int z=0;z<3;z++)eq.push_back({G+3*block+z,-a.Z(s,j,z)});lp.row(eq,0);for(auto&[id,v]:eq)v=-v;lp.row(eq,0);
 int prev=j?F+i-1:-1;
 for(double v:{ETA,1./ETA}){std::vector<std::pair<int,double>> row{{F+i,v},{R+i,-1},{U+i,-1}};if(j)row.push_back({prev,-v});lp.row(row,-a.N(s,j)+(j?0:v*E));}
 if(j){lp.row({{F+i,1},{prev,-1}},ETA*M);lp.row({{F+i,-1},{prev,1}},M/ETA);}else{lp.row({{F+i,1}},E+ETA*M);lp.row({{F+i,-1}},M/ETA-E);}
 if(j==T-1){if(a.end==YEAR){lp.p.col_lower_[F+i]=lp.p.col_upper_[F+i]=INITIAL;}else if(!curved)lp.p.col_cost_[F+i]=-prob*lambda;}
 }
 Terminal terminal=terminal_model(data,a.asof,a.end,k,cfg,lambda);
 if(curved){for(int s=0;s<S;s++){lp.p.col_cost_[W+s]=a.w[s];for(size_t j=0;j+1<terminal.x.size();j++){double slope=(terminal.y[j+1]-terminal.y[j])/(terminal.x[j+1]-terminal.x[j]),b=terminal.y[j]-slope*terminal.x[j];lp.row({{F+s*T+T-1,slope},{W+s,-1}},-b);}}}
 lp.finish(N);Highs highs;std::string engine=std::getenv("MG_LP_SOLVER")?std::getenv("MG_LP_SOLVER"):"ipx_nc";
 highs.setOptionValue("output_flag",false);highs.setOptionValue("threads",1);
 highs.setOptionValue("solver",engine.rfind("hipo",0)==0?"hipo":engine=="simplex"?"simplex":"ipm");
 highs.setOptionValue("presolve",engine=="ipx_np"||engine=="ipx_nc"||engine=="hipo_np"?"off":"on");
 if(engine=="ipx_nc")highs.setOptionValue("run_crossover","off");
 if(engine=="hipo_np"||engine=="hipo_nc"){highs.setOptionValue("run_crossover","off");highs.setOptionValue("hipo_system","hybrid");}
 highs.setOptionValue("ipm_optimality_tolerance",1e-9);highs.setOptionValue("primal_feasibility_tolerance",1e-8);highs.setOptionValue("dual_feasibility_tolerance",1e-8);
 highs.passModel(lp.p);auto status=highs.run();bool numerical_retry=false;
 // The same absolute dual-gap acceptance check also triggers the existing numerical retry.
 auto numerical_certificate_ok=[&](){
 if(status==HighsStatus::kError||highs.getModelStatus()!=HighsModelStatus::kOptimal||highs.getInfo().max_primal_infeasibility>1e-6)return false;
 const auto& s0=highs.getSolution();double d0=0;
 for(int i=0;i<lp.p.num_row_;++i)d0+=s0.row_dual[i]*lp.p.row_upper_[i];
 for(int i=0;i<N;++i){double d=s0.col_dual[i];if(d>0&&lp.p.col_lower_[i]>-1e20)d0+=d*lp.p.col_lower_[i];if(d<0&&lp.p.col_upper_[i]<1e20)d0+=d*lp.p.col_upper_[i];}
 return std::isfinite(d0)&&std::abs(highs.getObjectiveValue()-d0)<.02;
};
if(!numerical_certificate_ok()){
  numerical_retry=true;highs.clearSolver();highs.setOptionValue("solver","ipm");highs.setOptionValue("run_crossover","on");highs.setOptionValue("presolve","on");status=highs.run();
 }
 check(status!=HighsStatus::kError&&highs.getModelStatus()==HighsModelStatus::kOptimal,"affine LP status "+highs.modelStatusToString(highs.getModelStatus()));
 if(std::getenv("MG_SOLVER_LOG"))std::cerr<<"SOLVER "<<engine<<" retry="<<numerical_retry<<" asof="<<a.asof<<" T="<<T<<" S="<<S<<" ipm="<<highs.getInfo().ipm_iteration_count<<" primal="<<highs.getInfo().max_primal_infeasibility<<" dual="<<highs.getInfo().max_dual_infeasibility<<" seconds="<<sec()-began<<'\n';
 const auto&sol=highs.getSolution();Plan z;z.lambda=lambda;z.objective=highs.getObjectiveValue();z.q.assign(sol.col_value.begin()+Q,sol.col_value.begin()+Q+T);z.r.assign(T,0);for(int j=0;j<T;j++)for(int s=0;s<S;s++)z.r[j]+=a.w[s]*sol.col_value[R+s*T+j];
 for(int i=0;i<lp.p.num_row_;i++){z.residual=std::max(z.residual,sol.row_value[i]-lp.p.row_upper_[i]);z.dual+=sol.row_dual[i]*lp.p.row_upper_[i];}
 for(int i=0;i<N;i++){z.residual=std::max({z.residual,lp.p.col_lower_[i]-sol.col_value[i],sol.col_value[i]-lp.p.col_upper_[i]});double d=sol.col_dual[i];if(d>0&&lp.p.col_lower_[i]>-1e20)z.dual+=d*lp.p.col_lower_[i];if(d<0&&lp.p.col_upper_[i]<1e20)z.dual+=d*lp.p.col_upper_[i];}z.gap=std::abs(z.objective-z.dual);check(z.residual<1e-5&&z.gap<.02,"LP certificate failed");z.seconds=sec()-began;return z;}
}
