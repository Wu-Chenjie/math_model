#include "../src/dynamic_selection.hpp"
#include <cassert>
#include <iostream>
int main(){
#ifndef B_BEARING_BINS
 std::cerr<<"FAIL bearing prediction bin sensitivity is not configurable\n";return 1;
#else
 using dynamic_selection::bearing_outcome;
 assert(bearing_outcome(41.9,4)==bearing_outcome(42.1,4));
 assert(bearing_outcome(41.9,2)!=bearing_outcome(42.1,2));
 for(int width:{1,2,3,4,6,8,12})for(double a:{-361.,-1.,0.,41.99,180.,359.99,360.,721.}){
  int b=bearing_outcome(a,width);assert(b>=10&&b<10+360/width);assert(b==bearing_outcome(a+720,width));
 }
 std::cout<<"PASS bearing bins: angular wrap and configurable finite observation resolution\n";
#endif
}
