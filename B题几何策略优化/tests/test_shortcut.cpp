#include "../src/policy.hpp"
#if __has_include("../src/shortcut_sensor.hpp")
#include "../src/shortcut_sensor.hpp"
#endif
#include <iostream>
#include <cassert>
struct Probe:Sensor{geo::Pt position;double length=0;Reading measure(geo::Pt q,int)override{length+=geo::dist(position,q);position=q;return {0,0};}bool clear(geo::Pt q,int)override{length+=geo::dist(position,q);position=q;return true;}};
int main(){
#ifndef B_SHORTCUT_SENSOR
 std::cerr<<"FAIL guaranteed clear still travels to nominal center\n";return 1;
#else
 Probe original;ShortcutSensor sensor(original);geo::Poly region{{99,-1},{101,-1},{101,1},{99,1}};
 sensor.audit(1,region);assert(sensor.clear({100,0},1));
 assert(original.position.x>80&&original.position.x<83);for(auto v:region)assert(geo::dist(original.position,v)<20);
 sensor.measure({-100,100},2);assert(geo::dist(original.position,{-100,100})==0);
 assert(original.length<100+geo::dist({100,0},{-100,100}));assert(sensor.saved_distance()>0);
 sensor.audit(2,{{0,0},{100,0},{0,100}});sensor.clear({0,0},2);assert(geo::dist(original.position,{0,0})==0);
 sensor.audit(3,{{20,0}});sensor.clear({0,0},3);assert(geo::dist(original.position,{0,0})==0);
 Probe disabled;ShortcutSensor off(disabled,false);off.audit(1,region);off.clear({100,0},1);assert(disabled.position.x==100);
 std::cout<<"PASS clear shortcut: guaranteed support, unchanged measurements, insufficient support unchanged and path dominance\n";
#endif
}
