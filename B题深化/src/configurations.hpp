#pragma once
#include "policy.hpp"
inline Options configuration(int method){
 Options o;
 if(method>=1){o.spacing=999;o.shifted=true;o.shiftA=1./6;o.shiftB=11./12;o.includeOrigin=false;o.routing=2;o.opportunistic=true;}
 if(method==2)o.fixedLayout=21;
 return o;
}
