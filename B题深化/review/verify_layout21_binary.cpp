#include "certified_layout21_hex.hpp"
#include <iomanip>
#include <iostream>
int main(){for(auto p:certified_layout21::points)std::cout<<std::hexfloat<<p.x<<","<<p.y<<"\n";}
