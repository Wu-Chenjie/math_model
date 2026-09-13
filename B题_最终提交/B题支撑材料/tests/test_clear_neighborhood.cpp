#include "../src/dynamic_selection.hpp"
#include <cassert>
#include <iostream>
int main(){geo::Poly p{{-5,-5},{5,-5},{5,5},{-5,5}};auto points=dynamic_selection::safe_clear_points(p,{100,0});assert(!points.empty());double nearest=1e99;
 for(auto q:points){for(auto z:p)assert(geo::dist(q,z)<=20);nearest=std::min(nearest,geo::dist(q,{100,0}));}assert(nearest<90);
 auto here=dynamic_selection::safe_clear_points(p,{1,1});assert(geo::dist(here.front(),{1,1})<1e-8);
 assert(dynamic_selection::safe_clear_points({{-30,0},{30,0}},{100,0}).empty());std::cout<<"PASS safe clear neighborhoods cover all polygon vertices and avoid unnecessary center travel\n";
}
