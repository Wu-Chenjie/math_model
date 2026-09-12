#include "../src/policy.hpp"
#include <cassert>
#include <iostream>
struct Empty:Sensor{int nm=0;Reading measure(Pt,int)override{++nm;return{};}bool clear(Pt,int)override{assert(false);return false;}};
int main(){Empty s;Options o;o.fixedLayout=21;o.routing=2;o.opportunistic=true;Policy b(s,4,o);assert(b.covering_points().size()==21);b.run();assert(s.nm==420);assert(b.certificate=="convex_mesh_per_channel");std::cout<<"21-point selection and channel certificate passed\n";}
