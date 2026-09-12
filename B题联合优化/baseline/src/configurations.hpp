#pragma once
#include "policy.hpp"
inline Options configuration(int method){
 Options o;o.fixedLayout=21;o.routing=2;o.opportunistic=true;
 if(method==1){o.secondA=850;o.secondB=400;}
 if(method==2){o.secondA=843.1178;o.secondB=545.4003;}
 if(method>=3)o.stop_when_found16=true;
 if(method==4)o.route_model=1;
 if(method==5)o.route_model=2;
 return o;
}
