#include "../src/geometry.hpp"
#include <cassert>
#include <iostream>
using namespace geo;
int main(){
  Poly tri={{0,0},{40,0},{20,20*sqrt(3.)}};
  assert(std::abs(diameter(tri)-40)<1e-8);
  assert(std::abs(mec(tri).r-40/sqrt(3.))<1e-8);
  Poly p=outer_disk({0,0},1800,96);
  p=observe(p,{0,0},359.99,1.005);
  Pt truth=polar(1499,0.98);
  assert(contains(p,truth));
  p=clip(p,{1,0},1000);
  assert(!contains(p,{1100,0}));
  assert(contains(p,{500,0}));
  auto c=mec(Poly{{-10,0},{10,0},{0,0}});
  assert(std::abs(c.r-10)<1e-8);
  auto h=halfplanes({{{1,0},1},{{-1,0},1},{{0,1},1},{{0,-1},1}});
  assert(h.kind=="bounded" && std::abs(diameter(h.p)-sqrt(8.))<1e-8);
  assert(halfplanes({{{1,0},-1},{{-1,0},-1}}).kind=="empty");
  assert(halfplanes({{{1,0},1}}).kind=="unbounded");
  // A very thin but bounded parallelogram must not be called unbounded.
  assert(halfplanes({{{1,0},1},{{-1,0},1},{{1,1e-13},1},{{-1,-1e-13},1}}).kind=="numerically_uncertain");
  std::cout<<"geometry checks passed\n";
}
