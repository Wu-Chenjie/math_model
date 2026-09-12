#include "../src/discovery.hpp"
#include "../review/certified_layout21_hex.hpp"
#include <cassert>
#include <iostream>
int main(){discovery::Belief b(4);assert(b.size()==2048);assert(b.probability({0,0})>0&&b.probability({0,0})<1);b.negative_scan({0,0});assert(b.probability({0,0})==0&&b.size()<2048);
 for(auto p:certified_layout21::points)b.negative_scan({p.x,p.y});assert(b.size()==0&&b.probability({500,500})==0);
 std::cout<<"PASS discovery model conditions only on completed common scans; empty finite support reports zero probability, not completion\n";
}
