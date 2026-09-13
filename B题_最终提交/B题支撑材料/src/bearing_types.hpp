#pragma once
#include "geometry.hpp"
namespace dynamic_selection {
struct Event {geo::Pt q;int kind;double angle=0;};
struct Hypothesis {geo::Pt z;double radius;bool directional;double heading;double weight;};
}
