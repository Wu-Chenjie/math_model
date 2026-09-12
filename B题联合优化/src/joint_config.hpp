#pragma once
#include "configurations.hpp"
inline Options joint_configuration(int method,int problem){
 if(method>=55&&method<=57){auto o=joint_configuration(method==55?38:39,problem);if(problem==4)o.adaptive_optical=true;if(method==57)o.optical_weight=.5;return o;}
 if(method==53||method==54){auto o=joint_configuration(39,problem);if(problem==4)o.dynamic_limit=method==53?10:14;return o;}
 if(method>=50&&method<=52){auto o=joint_configuration(39,problem);o.discovery_weight=method==50?.25:method==51?.5:1.;return o;}
 if(method>=45&&method<=49){auto o=joint_configuration(method==48?40:method==49?42:39,problem);o.immediate_fee_weight=method==45?.25:method==47?1:.5;return o;}
 if(method>=40&&method<=44){auto o=joint_configuration(method==41?38:39,problem);if(method==40||method==41||method==44)o.use_lns=true;if(method==42||method==44)o.optical_weight=.5;if(method==43)o.optical_weight=.25;return o;}
 if(method==39){auto o=joint_configuration(38,problem);o.weighted_optical=true;return o;}
 if(method==38)return joint_configuration(problem==3?32:27,problem);
 if(method>=34&&method<=37){auto o=joint_configuration(method==34||method==37?29:method==35?21:27,problem);o.defer_single=true;if(method==36)o.auxiliary=1;if(method==37)o.q3_radius=1200;return o;}
 if(method==32||method==33){auto o=joint_configuration(method==32?29:27,problem);o.clear_neighborhood=true;return o;}
 auto o=configuration(5);o.dynamic_depth=2;o.active_mode=problem==3?1:0;
 if(method==1)o.auxiliary=1;
 if(method==2)o.joint_actions=true;
 if(method==3){o.auxiliary=1;o.joint_actions=true;}
 if(method==4)o.route_model=1;
 if(method==5){o.auxiliary=2;o.joint_actions=true;}
 if(method==6){o.auxiliary=2;}
 if(method>=7){o.auxiliary=2;o.joint_actions=true;}
 if(method==7)o.start_residual=.5;
 if(method==8)o.start_residual=1;
 if(method==9)o.start_residual=2;
 if(method==10)o.retreat=true;
 if(method==11){o.retreat=true;o.start_residual=1;}
 if(method==12){o.auxiliary=0;o.direct_optical=true;}
 if(method==13){o.direct_optical=true;o.optical_rotate=true;}
 if(method==14){o.candidate_menu=true;}
 if(method==15){o.candidate_menu=true;o.complete_source=true;}
 if(method==16){o.candidate_menu=true;o.complete_source=true;o.direct_optical=true;o.optical_rotate=true;}
 if(method==17){o.auxiliary=0;o.direct_optical=true;o.optical_rotate=true;}
 if(method==18){o.auxiliary=0;o.direct_optical=true;o.retreat=true;}
 if(method==19){o.auxiliary=3;o.joint_actions=false;}
 if(method==20){o.auxiliary=3;}
 if(method==21){o.auxiliary=4;o.direct_optical=true;}
 if(method==22){o.auxiliary=4;o.joint_actions=false;}
 if(method>=23){o.auxiliary=0;o.direct_optical=true;}
 if(method==23||method==24||method==25||method==26||method==28)o.dynamic_depth=3;
 if(method==24)o.optical_rotate=true;
 if(method==25)o.candidate_menu=true;
 if(method==26){o.candidate_menu=true;o.complete_source=true;}
 if(method==27||method==28)o.planning_samples=63;
 if(method==29){o.q3_radius=1124;o.candidate_menu=true;o.auxiliary=2;o.direct_optical=false;}
 if(method==30){o.q3_radius=1124;o.dynamic_depth=3;o.optical_rotate=true;}
 if(method==31){o.q3_radius=1150;o.candidate_menu=true;o.auxiliary=2;o.direct_optical=false;}
 return o;
}
