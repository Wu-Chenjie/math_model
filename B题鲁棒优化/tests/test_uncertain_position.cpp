#include "../src/position_uncertainty.hpp"
#include <cassert>
#include <iostream>
int main(){
 geo::Pt actual={0,.4};auto truth=actual+geo::polar(1500,1.005);
 auto p=position_error::update(geo::outer_disk({0,0},1800),{0,0},0,.4);
 assert(geo::contains(p,truth));
 assert(!geo::contains(geo::observe(geo::outer_disk({0,0},1800),{0,0},0),truth));
 assert(position_error::grid_side(.4)/sqrt(2.)+.4<20);
 std::cout<<"uncertain station position test passed\n";
}
