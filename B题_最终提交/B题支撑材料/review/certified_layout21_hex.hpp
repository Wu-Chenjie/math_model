// Exactly the binary64 coordinates independently certified by the interval-arithmetic
// producer. The certified leaf-box witness ships as artifacts/residual-witness.json
// (21 sites, 4564 certified leaf boxes) and is replayed by tests/replay_residual_fraction.py.
#pragma once
#include <array>
namespace certified_layout21 {
struct Point { double x,y; };
inline constexpr std::array<Point,21> points = {{
    {0x0.0p+0, 0x0.0p+0},
    {0x1.f180000000000p+9, 0x0.0p+0},
    {0x1.5fc91ea18215dp+9, 0x1.5fc91ea18215dp+9},
    {0x0.0p+0, 0x1.f180000000000p+9},
    {-0x1.5fc91ea18215dp+9, 0x1.5fc91ea18215dp+9},
    {-0x1.f180000000000p+9, 0x0.0p+0},
    {-0x1.5fc91ea18215dp+9, -0x1.5fc91ea18215dp+9},
    {0x0.0p+0, -0x1.f180000000000p+9},
    {0x1.5fc91ea18215dp+9, -0x1.5fc91ea18215dp+9},
    {0x1.d200000000000p+10, 0x0.0p+0},
    {0x1.93915dd785dc9p+10, 0x1.d200000000000p+9},
    {0x1.d200000000000p+9, 0x1.93915dd785dc9p+10},
    {0x0.0p+0, 0x1.d200000000000p+10},
    {-0x1.d200000000000p+9, 0x1.93915dd785dc9p+10},
    {-0x1.93915dd785dc9p+10, 0x1.d200000000000p+9},
    {-0x1.d200000000000p+10, 0x0.0p+0},
    {-0x1.93915dd785dc9p+10, -0x1.d1ffffffffff7p+9},
    {-0x1.d200000000009p+9, -0x1.93915dd785dc4p+10},
    {0x0.0p+0, -0x1.d200000000000p+10},
    {0x1.d200000000000p+9, -0x1.93915dd785dc9p+10},
    {0x1.93915dd785dc4p+10, -0x1.d200000000009p+9},
}};
}
