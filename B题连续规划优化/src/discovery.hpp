#pragma once
#include "dynamic_selection.hpp"
namespace discovery {
class Belief {
 std::vector<dynamic_selection::Hypothesis> particles;
 public:
 Belief()=default;
 explicit Belief(int problem){for(int i=1;i<=2048;++i){double r=1800*sqrt(dynamic_selection::radical(i,2)),a=360*dynamic_selection::radical(i,3);particles.push_back({geo::polar(r,a),1000+500*dynamic_selection::radical(i,5),problem==4&&dynamic_selection::radical(i,11)<.5,360*dynamic_selection::radical(i,7),1});}}
 size_t size()const{return particles.size();}
 double probability(geo::Pt q)const{if(particles.empty())return 0;int yes=0;for(auto h:particles)yes+=dynamic_selection::receives(h,q);return double(yes)/particles.size();}
 void negative_scan(geo::Pt q){particles.erase(std::remove_if(particles.begin(),particles.end(),[&](auto h){return dynamic_selection::receives(h,q);}),particles.end());}
};
}
