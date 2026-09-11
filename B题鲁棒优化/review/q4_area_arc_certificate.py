"""Exact-rational certificate: fixed universal Q4 designs need at least 15 sites.

Uses upper Riemann sums for two-disk overlap area and rational Taylor bounds
for the boundary arc. No floating point is used in any acceptance condition.
"""
from fractions import Fraction as F
from math import isqrt
import json
import sys

R,L=1800,1000
K=F(138,100)
SCALE=10**12

def atan_bounds(inv,n):
    x=F(1,inv)
    v=sum(((-1)**j*x**(2*j+1)/F(2*j+1) for j in range(n)),F(0))
    tail=(-1)**n*x**(2*n+1)/F(2*n+1)
    return min(v,v+tail),max(v,v+tail)

a,b=atan_bounds(5,25)
c,d=atan_bounds(239,8)
PI_LO=16*a-4*d
PI_HI=16*b-4*c
assert PI_LO>F('3.14159')

def cos_bounds(x):
    x=F(x);assert 0<=x<=F('0.508')
    term=F(1);total=term
    for j in range(1,24):
        term*=-x*x/F((2*j-1)*(2*j))
        total+=term
    tail=term*(-x*x)/F(47*48)
    return min(total,total+tail),max(total,total+tail)

def sqrt_upper(n):
    assert n>=0
    v=n*SCALE*SCALE
    root=isqrt(v)
    if root*root<v:root+=1
    return F(root,SCALE)

def overlap_upper(r):
    # f(y)=[sqrt(R²-y²)+sqrt(L²-y²)-r]_+ is nonincreasing on [0,L].
    # Thus the unit-spaced LEFT rectangle sum is an UPPER integral bound.
    total=F(0)
    for y in range(L):
        total+=max(F(0),sqrt_upper(R*R-y*y)+sqrt_upper(L*L-y*y)-r)
    return 2*total

def main():
    # On r<=sqrt(R²+L²), delta(r)=acos(R/r). For all r, delta(r)<=atan(L/R).
    edges=[1800,1900,1950,2000,2025,2050,2800]
    angle_upper=[F('0.326'),F('0.395'),F('0.452'),F('0.476'),F('0.4991'),F('0.508')]
    records=[]
    for lo,hi,u in zip(edges,edges[1:],angle_upper):
        clo,chi=cos_bounds(u)
        assert clo>0 and u<PI_LO/2
        if hi<=2050:
            assert hi*hi<R*R+L*L
            assert chi<=F(R,hi)
            angle_method='cos(upper)<=R/right_endpoint'
        else:
            assert chi*chi<=F(R*R,R*R+L*L)
            angle_method='global delta<=atan(L/R)<upper'
        area=overlap_upper(lo)
        deficit=1-area/(PI_LO*L*L)
        slack=deficit-K*u
        assert slack>0
        records.append({'r_interval_m':[lo,hi],'overlap_area_upper_m2':float(area),
                        'deficit_lower':float(deficit),'delta_upper_rad':str(u),
                        'verified_slack_lower':float(slack),'angle_method':angle_method,
                        'exact_area_upper':str(area)})
    n_lower=F(3*R*R,L*L)+K*PI_LO
    assert n_lower>14
    result={'statement':'N >= 15 for every finite fixed universal directional-reception site set',
            'source_disk_radius_m':R,'minimum_reception_radius_m':L,'k':str(K),
            'pi_lower':str(PI_LO),'riemann_step_m':1,'intervals':records,
            'N_real_lower':float(n_lower),'N_integer_lower':15,
            'scope':'All source positions in the radius-1800 disk and all closed 180-degree emission orientations; fixed finite sites; no optical fallback or adaptation counted as sites.'}
    with open(sys.argv[1] if len(sys.argv)>1 else 'q4_area_arc_certificate.json','w',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='pi_lower'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
