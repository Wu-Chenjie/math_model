#pragma once
#include "optical_terminal.hpp"
#define B_OPTICAL_PORTFOLIO 1
namespace optical_portfolio {
inline geo::Poly choose(const geo::Poly& incumbent,const geo::Poly&candidate,geo::Pt now,const std::vector<dynamic_selection::Hypothesis>&h,double fraction,double seconds){
 if(h.empty()||candidate.empty())return incumbent;
 double before=optical_terminal::expected(incumbent,now,h),after=optical_terminal::expected(candidate,now,h);
 return after<before*(1-fraction)&&before-after>seconds?candidate:incumbent;
}
}
