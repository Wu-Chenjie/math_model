#include "../src/residual_cover.hpp"
#include "../review/certified_layout21_hex.hpp"
#include <iostream>
int main(){geo::Poly p;for(auto q:certified_layout21::points)p.push_back({q.x,q.y});auto c=residual_cover::certify(p);std::cout<<c.pass<<" "<<c.checks<<" "<<c.leaves.size()<<"\n";}
