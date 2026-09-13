#pragma once
// Included after Sensor/Reading declarations in policy.hpp.
struct RolloutSensor:Sensor {
 dynamic_selection::Hypothesis source;Pt pos;int channel;double error,time=0;bool cleared=false;
 std::vector<dynamic_selection::Event>events;
 RolloutSensor(dynamic_selection::Hypothesis h,Pt p,int k,double e,const std::vector<dynamic_selection::Event>&history):source(h),pos(p),channel(k),error(e),events(history){}
 void move(Pt p){time+=geo::dist(pos,p)/5;pos=p;}
 Reading measure(Pt p,int k)override{move(p);time+=5+(channel!=k);channel=k;if(cleared)return {};
  for(auto e:events)if(e.kind<=2&&geo::dist(p,e.q)<1e-7)return {e.kind,e.angle};
  Reading r;if(dynamic_selection::receives(source,p)){if(geo::dist(source.z,p)<=5)r.kind=1;else{r.kind=2;r.angle=fmod(atan2(source.z.y-p.y,source.z.x-p.x)*180/geo::pi+error+720,360);}}
  events.push_back({p,r.kind,r.angle});return r;
 }
 bool clear(Pt p,int)override{move(p);bool ok=!cleared&&geo::dist(p,source.z)<=20;time+=ok?5:3;if(ok)cleared=true;return ok;}
};
