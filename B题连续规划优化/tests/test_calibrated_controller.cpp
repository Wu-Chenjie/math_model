#include "../src/joint_config.hpp"
#include <iostream>
int main(){auto improved=joint_configuration(58,4);
 if(!improved.adaptive_optical||!improved.weighted_optical){std::cerr<<"FAIL calibrated configuration is not based on current method56\n";return 1;}
 if(joint_configuration(56,4).planning_samples!=63)return 1;
 std::cout<<"PASS calibrated controller keeps adaptive coverage and posterior ordering\n";
}
