"""Exact-rational minimax audit on the FULL robust reception domain.

Trigonometric enclosures: Machin pi + Taylor alternating-series remainders.
Floating-point centers are proposals only; every leaf is accepted by exact
rational squared-distance checks. No library floating trig is trusted.
"""
from fractions import Fraction as F
from functools import lru_cache
from math import hypot, isqrt
import json
import sys

S = 10**20

def rounded_interval(lo, hi):
    return F((lo*S).__floor__(), S), F((hi*S).__ceil__(), S)

def atan_interval(inv, n):
    x = F(1, inv)
    v = sum(((-1)**k*x**(2*k+1)/F(2*k+1) for k in range(n)), F(0))
    tail = (-1)**n*x**(2*n+1)/F(2*n+1)
    return min(v,v+tail),max(v,v+tail)

a,b=atan_interval(5,45)
c,d=atan_interval(239,14)
PI_LO,PI_HI=rounded_interval(16*a-4*d,16*b-4*c)

@lru_cache(None)
def trig(degrees, cosine=False):
    degrees=F(degrees)
    lo,hi=sorted((degrees*PI_LO/180,degrees*PI_HI/180))
    x=F(((lo+hi)*S/2).__floor__(),S)
    err=max(abs(x-lo),abs(x-hi))
    term=F(1) if cosine else x
    v=term
    for k in range(1,32):
        term *= -x*x/F((2*k-1)*(2*k) if cosine else (2*k)*(2*k+1))
        v += term
    k=32
    tail=term*(-x*x)/F((2*k-1)*(2*k) if cosine else (2*k)*(2*k+1))
    # |x|<4 here, so the omitted alternating tail decreases in magnitude.
    assert abs(x)<4
    return rounded_interval(min(v,v+tail)-err,max(v,v+tail)+err)

class I:
    def __init__(self,a,b=None):self.a=F(a);self.b=F(a if b is None else b)
    def __add__(x,y):
        y=as_i(y);return I(x.a+y.a,x.b+y.b)
    __radd__=__add__
    def __neg__(x):return I(-x.b,-x.a)
    def __sub__(x,y):return x+-as_i(y)
    def __rsub__(x,y):return as_i(y)+-x
    def __mul__(x,y):
        y=as_i(y);v=[x.a*y.a,x.a*y.b,x.b*y.a,x.b*y.b];return I(min(v),max(v))
    __rmul__=__mul__
    def __truediv__(x,y):
        y=as_i(y);assert y.a*y.b>0;return x*I(1/y.b,1/y.a)
    def sq(x):
        assert x.a>=0;return I(x.a*x.a,x.b*x.b)
    def pair(x):return [float(x.a),float(x.b)]

def as_i(x):return x if isinstance(x,I) else I(x)
def sin(x):return I(*trig(x))
def cos(x):return I(*trig(x,True))
def sqrt_bounds(x):
    lo=isqrt((x.a*S*S).__floor__())
    hi=isqrt((x.b*S*S).__ceil__())+1
    return I(F(lo,S),F(hi,S))

def global_lower(e1,e2,t_upper,claimed_floor):
    R=1500; eps=F('1.005'); T=F(t_upper)
    k=sin(e1+2*e2);h=cos(e1+2*e2);s=sin(2*e2);l=sin(2*e1+2*e2)
    # Every q in G has 0<=a<=1005, |b|<=1005, norm(q)<=1005.
    # b<=30 is handled by the fixed normal-readout witness pair (1340,0),(1500,0).
    # Their angle difference has positive dot product and tan(delta)<=4800/165825.
    assert F(4800,165825)<(sin(2*e2)/cos(2*e2)).a
    # b>=30: denominator positive, B on the forward rotated ray, r_B>5,
    # and |B-q|>5 so neither witness triggers the near response.
    denlo=(R*l-1005*k).a
    denhi=(R*l+1005*h).b
    tlo=(R*h*30-s*1005**2).a/denhi
    lambda_lo=(30*cos(e1)-1005*sin(e1)).a/denhi
    assert denlo>0 and tlo>5
    assert (R*h-1005).a>0  # x-component of rotated A-q is positive
    assert lambda_lo*(R-1005)>5
    assert T<(R*cos(2*e1)).a
    # N-T*D = -s*||q||^2 + w.q - T*R*l. G is contained in
    # disk(center=(5cos(eps),-5sin(eps)), radius=1000).
    cx,cy=5*cos(eps),-5*sin(eps)
    wx,wy=k*(R+T),h*(R-T)
    gx,gy=wx-2*s*cx,wy-2*s*cy
    assert gx.a>0 and gy.a>0
    gnorm=sqrt_bounds(gx.sq()+gy.sq())
    assert gnorm.a>(2000*s).b
    # Norm(center)^2=25 exactly. The quadratic maximum occurs at radius 1000.
    quad_max=-s*(1000000+25)+wx*cx+wy*cy-T*R*l+1000*gnorm
    assert quad_max.b<=0, ('increase t_upper',quad_max.pair())
    rad=sqrt_bounds(I(R*R)+I(T*T)-2*R*T*cos(2*e1))/2
    assert rad.a>=F(claimed_floor)
    assert F(claimed_floor)<80
    return {'certified_floor_m':claimed_floor,'global_lower_m':rad.pair(),
            't_upper_m':t_upper,'quadratic_max_upper':float(quad_max.b),
            'positive_denominator_lower':float(denlo),'witness_r_lower_m':float(tlo),
            'witness_second_distance_lower_m':float(lambda_lo*(R-1005)),
            'small_b_witness_radius_m':80}

def reception(q):
    a,b=map(F,q); eps=F('1.005')
    d=a*cos(eps)-abs(b)*sin(eps); normsq=a*a+b*b
    c1=2000*d-normsq;c2=999975+10*d-normsq
    assert c1.a>=0 and c2.a>=0
    return {'q':[str(a),str(b)],'r1000_constraint_margin_m2':c1.pair(),
            'r5_constraint_margin_m2':c2.pair()}

def clip(poly, normal, rhs):
    out=[]
    for i,x in enumerate(poly):
        y=poly[(i+1)%len(poly)]
        f=sum(normal[j]*x[j] for j in range(2))-rhs
        g=sum(normal[j]*y[j] for j in range(2))-rhs
        if f<=0:out.append(x)
        if (f<=0)!=(g<=0):
            t=f/(f-g);out.append(tuple(x[j]+t*(y[j]-x[j]) for j in range(2)))
    return out

def center_proposal(poly):
    p=[tuple(map(float,z)) for z in poly]
    if not p:return (F(0),F(0))
    # Any center is permitted. Select best among pair midpoints and circumcenters.
    candidates=list(p)
    for i,a in enumerate(p):
        for j,b in enumerate(p[:i]):
            candidates.append(((a[0]+b[0])/2,(a[1]+b[1])/2))
            for c in p[:j]:
                ux,uy=b[0]-a[0],b[1]-a[1];vx,vy=c[0]-a[0],c[1]-a[1]
                d=2*(ux*vy-uy*vx)
                if abs(d)>1e-15:
                    uu=ux*ux+uy*uy;vv=vx*vx+vy*vy
                    candidates.append((a[0]+(uu*vy-vv*uy)/d,a[1]+(ux*vv-vx*uu)/d))
    center=min(candidates,key=lambda c:max(hypot(c[0]-z[0],c[1]-z[1]) for z in p))
    return tuple(F(f"{v:.12f}") for v in center)

def certify_fixed_q(bound=F('55.739')):
    q=(F('843.1178'),F('545.4003'));eps=F('1.005')
    # Outer triangle plus the exact disk tangents at +/-eps (with rational
    # coefficient error allowances). This contains every point of the arc.
    tangent=sin(eps).b/cos(eps).a
    first=[(F(0),F(0)),(F(1500),-1500*tangent),(F(1500),1500*tangent)]
    for angle in [-eps,eps]:
        nx,ny=cos(angle),sin(angle)
        normal=((nx.a+nx.b)/2,(ny.a+ny.b)/2)
        pad=3000*((nx.b-nx.a)+(ny.b-ny.a))/2
        first=clip(first,normal,F(1500)+pad)
    stack=[(F(-182+23*k),F(-182+23*(k+1))) for k in range(8)]
    leaves=[];nodes=0
    while stack:
        lo,hi=stack.pop();mid=(lo+hi)/2;half=(hi-lo)/2
        poly=first
        for angle,sign in [(mid+eps+half,1),(mid-eps-half,-1)]:
            si,co=sin(angle),cos(angle)
            nx,ny=-si*sign,co*sign
            normal=((nx.a+nx.b)/2,(ny.a+ny.b)/2)
            # Every source has |z_x-q_x|, |z_y-q_y|<3000.
            pad=3000*((nx.b-nx.a)+(ny.b-ny.a))/2
            rhs=sum(normal[j]*q[j] for j in range(2))+pad
            poly=clip(poly,normal,rhs)
        nodes+=1
        center=center_proposal(poly)
        sq=max((sum((z[j]-center[j])**2 for j in range(2)) for z in poly),default=F(0))
        if sq<=bound*bound:
            leaves.append({"lo":str(lo),"hi":str(hi),"center":[str(v) for v in center],"vertices":len(poly)})
        else:
            assert hi-lo>F(1,10**12),"Requested radius is too small for this outer triangle"
            stack.extend([(lo,mid),(mid,hi)])
    leaves.sort(key=lambda a:F(a['lo']))
    assert F(leaves[0]['lo'])==-182 and F(leaves[-1]['hi'])==2
    assert all(x['hi']==y['lo'] for x,y in zip(leaves,leaves[1:]))
    return {"q":[str(v) for v in q],"upper_m":str(bound),"verified_by":"exact Fraction squared-distance checks", "nodes":nodes,"leaves":leaves}

if __name__=='__main__':
    # Tiny inward margins avoid first-reading rounding ties and ensure the
    # physical quantized witnesses are feasible under an unknown tie rule.
    e1=F('1.00499999')
    result={"reception":reception(['843.1178','545.4003']),
            "continuous_model_lower":global_lower(e1,F('1.00499999'),'1400.796371','55.73823'),
            "physical_quantized_lower":global_lower(e1,F('0.99999999'),'1400.99','55.6528'),
            "continuous_and_quantized_upper":certify_fixed_q()}
    with open(sys.argv[1] if len(sys.argv)>1 else 'q2_rational_certificate.json','w',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:({kk:vv for kk,vv in v.items() if kk!='leaves'}) for k,v in result.items()},ensure_ascii=False,indent=2))
