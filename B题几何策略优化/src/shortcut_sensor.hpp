#pragma once
#include "policy.hpp"
#define B_SHORTCUT_SENSOR 1
// Execution adapter: the controller retains its original route anchors, while
// physical clear commands may stop earlier on the incoming segment. Measurements
// are never moved. With nominal conservative support, clear outcomes are unchanged.
// Construct only for a fresh session starting at (0,0), never attach mid-session.
class ShortcutSensor:public Sensor {
 Sensor& io;bool enabled;std::array<geo::Poly,21> support;
 geo::Pt physical,anchor;double physical_length=0,anchor_length=0;
 bool fits(const geo::Poly& p,geo::Pt q)const{
  if(p.empty())return false;for(auto z:p)if(geo::dist(z,q)>20-1e-4)return false;return true;
 }
 void record(geo::Pt requested,geo::Pt executed){
  anchor_length+=geo::dist(anchor,requested);physical_length+=geo::dist(physical,executed);anchor=requested;physical=executed;
  if(physical_length+geo::dist(physical,anchor)>anchor_length+1e-5)throw std::runtime_error("shortcut violated anchored path dominance");
 }
 public:int shortcuts=0;
 explicit ShortcutSensor(Sensor& sensor,bool active=true):io(sensor),enabled(active){}
 Reading measure(geo::Pt q,int k)override{auto r=io.measure(q,k);record(q,q);return r;}
 bool clear(geo::Pt q,int k)override{
  geo::Pt target=q;
  if(enabled&&k>=1&&k<=20&&fits(support[k],q)){
   if(fits(support[k],physical))target=physical;
   else{double low=0,high=1;for(int i=0;i<60;++i){double mid=(low+high)/2;auto trial=physical+(q-physical)*mid;if(fits(support[k],trial))high=mid;else low=mid;}target=physical+(q-physical)*high;}
   // A fresh endpoint check handles arithmetic roundoff without assuming success.
   if(!fits(support[k],target))target=q;
  }
  bool result=io.clear(target,k);record(q,target);
  if(geo::dist(q,target)>1e-7){++shortcuts;if(!result)throw std::runtime_error("guaranteed shortcut clear failed");}
  if(result&&k>=1&&k<=20)support[k].clear();return result;
 }
 void audit(int k,const geo::Poly&p)override{if(k>=1&&k<=20)support[k]=p;io.audit(k,p);}
 void phase(int stage)override{io.phase(stage);}
 double saved_distance()const{return anchor_length-physical_length;}
};
