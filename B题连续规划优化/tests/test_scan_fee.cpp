#include "../src/simulator.hpp"
#include "../src/configurations.hpp"
#include <cassert>
#include <iostream>
int main(){Sim s({},1,0);Policy b(s,4,configuration(5));double expected=b.scan_fee();assert(expected==119);b.scan({0,0});assert(s.time==expected);expected=b.scan_fee();double before=s.time;b.scan({0,0});assert(s.time-before==expected);std::cout<<"PASS scanning charge equals simulator measurements plus actual switches\n";}
