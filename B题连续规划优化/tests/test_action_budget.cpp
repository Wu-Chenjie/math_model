#include "../src/simulator.hpp"
#include "../src/joint_config.hpp"
#include <cassert>
#include <iostream>
int main(){for(int p:{3,4}){auto o=joint_configuration(39,p);o.dynamic_limit=1;Sim s(make_case(p,73),73,0);Policy b(s,p,o);b.run();assert(s.success==s.total());assert(b.dynamic_actions<=s.total());}std::cout<<"PASS per-source dynamic budget persists across global replans\n";}
