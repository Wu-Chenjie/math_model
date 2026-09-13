#include "../src/optical_order.hpp"
#include <cassert>
#include <iostream>
int main(){geo::Poly cells;for(int i=0;i<20;++i)cells.push_back({i*25.,0});
 std::vector<dynamic_selection::Hypothesis> h{{{250,0},1000,false,0,.99},{{475,0},1000,false,0,.01}};
 auto r=optical_order::choose(cells,{240,0},h);assert(r.size()==cells.size());assert(geo::dist(r.front(),{250,0})<30);
 auto sorted=r;auto less=[](auto a,auto b){return a.x!=b.x?a.x<b.x:a.y<b.y;};std::sort(sorted.begin(),sorted.end(),less);assert(sorted.size()==cells.size());for(size_t i=0;i<cells.size();++i)assert(geo::dist(cells[i],sorted[i])==0);
 auto empty=optical_order::choose(cells,{0,0},{});assert(empty.front().x==0);
 std::cout<<"PASS posterior sweep prioritizes likely location and retains every covering cell\n";
}
