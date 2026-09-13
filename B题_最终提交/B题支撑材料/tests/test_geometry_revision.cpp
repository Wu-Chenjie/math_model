#include "../src/policy.hpp"
#include <cassert>
#include <fstream>
#include <iomanip>
#include <iostream>
int main(int argc,char**argv){
 if(argc!=2){std::cerr<<"usage: test_geometry_revision OUTPUT_WITNESS.json\n";return 2;}
 auto p=geo::observe(geo::outer_disk({0,0},1800),{0,0},0);p=geo::disk_clip(p,{0,0},1500);p=geo::clip(p,{1,0},1500);
 int checks=0;double gap=0;
 for(auto q:geo::Poly{{750,300},{810,-480},{300,0},{0,600},{1400,10}}){auto b=robust_geometry::worst_radius(p,q,512,.01);auto range=robust_geometry::angles(p,q);double sampled=0;
  for(int i=0;i<=5000;++i){double angle=range.first+(range.second-range.first)*i/5000;auto region=geo::observe(p,q,angle);if(!region.empty())sampled=std::max(sampled,geo::mec(region).r);++checks;}
  assert(sampled<=b.upper+1e-6);assert(b.lower<=b.upper);gap=std::max(gap,b.upper-sampled);
 }
 std::vector<dynamic_selection::Event>history{{{0,0},2,0}};
 assert(robust_geometry::reception(p,{750,300},history,3));
 assert(!robust_geometry::reception(p,{750,300},history,4));
 assert(!robust_geometry::candidate(p,{0,0},{0,0},0,history,3,2).valid);
 std::vector<geo::Poly>cells;auto centers=adaptive_optical::cover(p,{0,0},0,&cells);assert(cells.size()==centers.size());
 auto moved=neighborhood_tour::optimize(centers,cells,{0,200});assert(neighborhood_tour::length(moved,{0,200})<=neighborhood_tour::length(centers,{0,200})+1e-7);
 for(size_t i=0;i<cells.size();++i){assert(neighborhood_tour::valid(moved[i],cells[i]));for(auto z:cells[i])assert(geo::dist(moved[i],z)<20);}
 geo::Poly sites;for(auto q:certified_layout21::points)sites.push_back({q.x,q.y});auto certificate=residual_cover::certify(sites);assert(certificate.pass);
 auto missing=sites;missing.erase(missing.begin()+9);assert(!residual_cover::certify(missing,certificate.leaves).pass);
 residual_cover::State state;std::vector<bool>visited(sites.size());state.leaves=certificate.leaves;
 geo::Pt shifted=state.replace(sites,visited,1,{850,50});assert(geo::dist(shifted,sites[1])>1);sites[1]=shifted;auto recert=residual_cover::certify(sites);assert(recert.pass);
 // Export actual accepted coordinates and interval-certified leaf boxes for
 // independent Fraction replay; doubles are round-trip decimal encoded.
 std::ofstream f(argv[1]);if(!f){std::cerr<<"cannot open witness output\n";return 3;}
 f<<std::setprecision(17)<<"{\"sites\":[";for(size_t i=0;i<sites.size();++i){if(i)f<<",";f<<"["<<sites[i].x<<","<<sites[i].y<<"]";}f<<"],\"boxes\":[";for(size_t i=0;i<recert.leaves.size();++i){auto b=recert.leaves[i];if(i)f<<",";f<<"["<<b.x0<<","<<b.y0<<","<<b.x1<<","<<b.y1<<"]";}f<<"]}\n";
 f.close();if(!f){std::cerr<<"cannot finish witness output\n";return 4;}
 std::cout<<"{\"status\":\"PASS\",\"angle_checks\":"<<checks<<",\"max_upper_gap_m\":"<<gap<<",\"optical_cells\":"<<cells.size()<<",\"static_leaves\":"<<certificate.leaves.size()<<",\"replacement_leaves\":"<<recert.leaves.size()<<",\"replacement_shift_m\":"<<geo::dist(shifted,geo::Pt{995,0})<<"}\n";
}
