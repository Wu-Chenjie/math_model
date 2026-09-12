"""Independent exact-rational triangle/disk classification (no production geometry)."""
from fractions import Fraction as F
import math, json
from pathlib import Path

H = F(999)
A, B = F(1, 6), F(11, 12)
# Store Cartesian (x, y/sqrt(3)); all metric squares remain rational.
def vertex(i, j):
    return (H * (i+A+(j+B)/2), H*(j+B)/2)
def sub(a, b): return (a[0]-b[0], a[1]-b[1])
def dot(a, b): return a[0]*b[0]+3*a[1]*b[1]
def cross(a, b): return a[0]*b[1]-a[1]*b[0]
def segment2(a,b):
    d=sub(b,a)
    t=max(F(0),min(F(1),-dot(a,d)/dot(d,d)))
    c=(a[0]+t*d[0],a[1]+t*d[1])
    return dot(c,c)
def triangle2(p):
    signs=[cross(sub(p[(k+1)%3],p[k]),(-p[k][0],-p[k][1])) for k in range(3)]
    if all(s>=0 for s in signs) or all(s<=0 for s in signs): return F(0)
    return min(segment2(p[k],p[(k+1)%3]) for k in range(3))

inside, outside, ids = [], [], set()
for i in range(-20,20):
    for j in range(-20,20):
        for kind, t in enumerate([[(i,j),(i+1,j),(i,j+1)],[(i+1,j+1),(i,j+1),(i+1,j)]]):
            p=[vertex(*v) for v in t]
            d2=triangle2(p)
            rec=(d2,i,j,kind)
            if d2<=1800**2:
                assert -6<=i<6 and -6<=j<6
                inside.append(rec); ids.update(t)
            else: outside.append(rec)
max_in=max(inside); min_out=min(outside)
assert len(ids)==25
rows=[]
for i,j in sorted(ids):
    x,y=vertex(i,j)
    rows.append(dict(i=i,j=j,x=float(x),y=float(y)*math.sqrt(3),radius=math.sqrt(float(dot((x,y),(x,y))))))
maxrow=max(rows,key=lambda x:x['radius'])
radius=math.ceil(max(maxrow['radius']+math.hypot(750,300),math.sqrt(2)*1800/math.cos(math.pi/64)))
nmeasure=25*20+16*9
nclear=16*111
nlong=25+16*12 # opportunistic measure is at the current location.
length=nlong*2*radius+16*107*28
time=length/5+6*nmeasure+3*nclear+32
result=dict(parameters=dict(h=999,shiftA='1/6',shiftB='11/12',includeOrigin=False),
    triangles=len(inside),points=len(rows),coordinates=rows,
    max_point=maxrow,
    farthest_retained_triangle=dict(index=max_in[1:],distance2=str(max_in[0]),distance=math.sqrt(float(max_in[0])),margin=1800-math.sqrt(float(max_in[0]))),
    nearest_excluded_triangle=dict(index=min_out[1:],distance2=str(min_out[0]),distance=math.sqrt(float(min_out[0])),margin=math.sqrt(float(min_out[0]))-1800),
    budget=dict(action_radius_m=radius,measures=nmeasure,clears=nclear,effective_actions=nmeasure+nclear+2,long_segments=nlong,move_m=length,time_s=time,time_h=time/3600))
out=Path(__file__).resolve().parents[1]/'layout_exact_certificate.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='coordinates'},ensure_ascii=False,indent=2))
