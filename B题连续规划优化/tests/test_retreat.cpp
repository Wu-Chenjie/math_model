#include "../src/dynamic_selection.hpp"
#include <cassert>
#include <iostream>
int main(){using namespace dynamic_selection;geo::Pt center{500,0};std::vector<Event> h{{{0,0},2,0}};auto q=retreat_points(center,h);assert(q.size()==4);
 for(auto p:q){assert(p.x>0&&p.x<500&&p.y==0);for(int angle=0;angle<360;++angle){Hypothesis source{center,1000,true,double(angle),1};if(receives(source,{0,0}))assert(receives(source,p));}}
 assert(retreat_points(center,{}).empty());std::cout<<"PASS retreat rays remain on received half-plane for fixed target across 360 headings\n";
}
