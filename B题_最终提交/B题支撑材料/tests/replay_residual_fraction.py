"""Independent exact-rational replay of accepted spatial witnesses.

No production interval predicate imported. JSON numbers are converted through
binary64, matching the robot's actual coordinates exactly, then to Fraction.
"""
import json,sys,time,hashlib
from fractions import Fraction as F
from pathlib import Path
start=time.monotonic();root=Path(__file__).resolve().parents[1]
witness=Path(sys.argv[1]) if len(sys.argv)>1 else root/'artifacts/residual-witness.json'
a=json.loads(witness.read_text())
P=[tuple(F(float(v)) for v in z) for z in a['sites']]
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def hull(p):
 p=sorted(set(p));lo=[];hi=[]
 for chain,points in [(lo,p),(hi,p[::-1])]:
  for q in points:
   while len(chain)>1 and cross(chain[-2],chain[-1],q)<=0:chain.pop()
   chain.append(q)
 return lo[:-1]+hi[:-1]
for raw in a['boxes']:
 x0,y0,x1,y1=map(lambda x:F(float(x)),raw);v=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
 safe=[p for p in P if all(sum((p[i]-z[i])**2 for i in [0,1])<=F('999.999')**2 for z in v)]
 h=hull(safe);assert len(h)>=3
 assert all(cross(h[i],h[(i+1)%len(h)],z)>=0 for i in range(len(h)) for z in v)
# Rebuild the dyadic partition to prove every disk-intersecting box is present,
# instead of trusting a list of successful leaves that might have gaps.
leaves={tuple(F(float(x)) for x in b) for b in a['boxes']};seen=0
stack=[(F(-1800),F(-1800),F(1800),F(1800))]
while stack:
 b=stack.pop();x0,y0,x1,y1=b
 if b in leaves:seen+=1;continue
 x=x0 if x0>0 else x1 if x1<0 else 0;y=y0 if y0>0 else y1 if y1<0 else 0
 if x*x+y*y>1800**2:continue
 assert max(x1-x0,y1-y0)>F(1,10000),'missing leaf'
 if x1-x0>=y1-y0:
  m=(x0+x1)/2;stack.extend([(x0,y0,m,y1),(m,y0,x1,y1)])
 else:
  m=(y0+y1)/2;stack.extend([(x0,y0,x1,m),(x0,m,x1,y1)])
assert seen==len(leaves)
out={'status':'PASS','arithmetic':'Python Fraction, independent of C++ interval code','sites':len(P),'verified_leaf_boxes':seen,'full_disk_partition':True,'witness_sha256':hashlib.sha256(witness.read_bytes()).hexdigest(),'runtime_s':time.monotonic()-start}
(root/'artifacts/residual-fraction-replay.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
