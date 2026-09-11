"""Exact rational robust certificate for all positions and hemispheres.

Input: JSON array [[x,y],...] or {"points":[[x,y],...]}. Decimal coordinates
are interpreted exactly as written. No production geometry is imported.
The disk is covered by a rational circumscribed tangent polygon; every leaf
triangle lies at least eta inside the convex hull of sites within reception
of all leaf vertices. With reception+eta <= 1000 this proves coverage after
every site is independently perturbed by any Euclidean vector of norm <=eta.
FAIL/UNKNOWN is not a proof that the proposed layout is infeasible.
"""
from fractions import Fraction as F
from decimal import Decimal
from pathlib import Path
import argparse,json,math,time
if not __debug__:raise RuntimeError('Certificate checking requires Python assertions; do not use -O.')

def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return(a[0]-b[0],a[1]-b[1])
def d2(a,b):return dot(sub(a,b),sub(a,b))
def hull(ids,points):
    ids=sorted(set(ids),key=lambda i:points[i])
    if len(ids)<=1:return ids
    lo=[];hi=[]
    for collection,seq in [(lo,ids),(hi,list(reversed(ids)))]:
        for i in seq:
            while len(collection)>=2 and cross(sub(points[collection[-1]],points[collection[-2]]),sub(points[i],points[collection[-1]]))<=0:collection.pop()
            collection.append(i)
    return lo[:-1]+hi[:-1]
def contains(poly,z):
    if len(poly)<3:return False # Only nondegenerate leaf triangles are certified.
    return all(cross(sub(poly[(i+1)%len(poly)],p),sub(z,p))>=0 for i,p in enumerate(poly))
def robust_contains(poly,z,eta):
    if len(poly)<3:return False
    for i,p in enumerate(poly):
        edge=sub(poly[(i+1)%len(poly)],p);area=cross(edge,sub(z,p))
        if area<0 or area*area<eta*eta*dot(edge,edge):return False
    return True
def outer_polygon(n,R):
    normals=[]
    for quadrant in range(4):
        for k in range(n):
            t=F(k,n);x,y=(1-t*t)/(1+t*t),2*t/(1+t*t)
            for j in range(quadrant):x,y=-y,x
            assert x*x+y*y==1
            normals.append((x,y))
    out=[]
    for i,a in enumerate(normals):
        b=normals[(i+1)%len(normals)];det=cross(a,b)
        assert det>0
        out.append((R*(b[1]-a[1])/det,R*(a[0]-b[0])/det))
    return out
def split(triangle):
    i=max(range(3),key=lambda k:d2(triangle[k],triangle[(k+1)%3]))
    a,b,c=triangle[i],triangle[(i+1)%3],triangle[(i+2)%3]
    m=((a[0]+b[0])/2,(a[1]+b[1])/2)
    return (a,m,c),(m,b,c)
def certify(points,n=128,maxdepth=30,reception=F(998),eta=F('0.1')):
    reception=F(reception);eta=F(eta);assert eta>=0 and 0<reception and reception+eta<=1000
    reception2=reception*reception;rf2=float(reception2)
    begin=time.time();outer=outer_polygon(n,F(1800));pf=[tuple(map(float,p)) for p in points]
    leaves=[];unresolved=[];nodes=0;minmargin=None;minhull=None
    for root in range(len(outer)):
        stack=[(((F(0),F(0)),outer[root],outer[(root+1)%len(outer)]),'')]
        while stack:
            tri,path=stack.pop();nodes+=1
            tf=[tuple(map(float,v)) for v in tri]
            candidates=[i for i,p in enumerate(pf) if all((p[0]-v[0])**2+(p[1]-v[1])**2<=rf2+1e-5 for v in tf)]
            safe=[i for i in candidates if all(d2(points[i],v)<=reception2 for v in tri)]
            hi=hull(safe,points);hp=[points[i] for i in hi]
            if all(robust_contains(hp,v,eta) for v in tri):
                margin=min(reception2-d2(points[i],v) for i in hi for v in tri)
                minmargin=margin if minmargin is None else min(minmargin,margin)
                clearance=min(cross(sub(hp[(i+1)%len(hp)],p),sub(v,p))**2/d2(hp[(i+1)%len(hp)],p) for i,p in enumerate(hp) for v in tri)
                minhull=clearance if minhull is None else min(minhull,clearance)
                leaves.append(dict(root=root,path=path,hull=hi))
            elif len(path)>=maxdepth:
                unresolved.append(dict(root=root,path=path,vertices=[[str(x) for x in v] for v in tri]))
                # Report a finite obstruction to this certificate rather than
                # exploding the unresolved part of a geometrically bad layout.
                if len(unresolved)>=16:break
            else:
                a,b=split(tri);stack.append((b,path+'1'));stack.append((a,path+'0'))
        if len(unresolved)>=16:break
    return dict(status='CERTIFIED' if not unresolved else 'UNKNOWN',points=[[str(x) for x in p] for p in points],
        radius=1800,reception=str(reception),perturbation_radius=str(eta),tangent_quadrant_subdivisions=n,maxdepth=maxdepth,
        outer_radius_upper_m=math.sqrt(float(max(dot(v,v) for v in outer))),
        nodes=nodes,leaf_count=len(leaves),min_squared_distance_margin=None if minmargin is None else str(minmargin),
        min_hull_clearance_squared=None if minhull is None else str(minhull),
        min_hull_clearance_m=None if minhull is None else math.sqrt(float(minhull)),
        elapsed_s=time.time()-begin,leaves=leaves,unresolved=unresolved)
def verify(cert):
    assert cert['status']=='CERTIFIED'
    points=[tuple(map(F,p)) for p in cert['points']]
    reception=F(cert['reception']);eta=F(cert['perturbation_radius'])
    assert cert['radius']==1800 and eta>=0 and reception>0 and reception+eta<=1000
    outer=outer_polygon(cert['tangent_quadrant_subdivisions'],F(1800))
    records={(row['root'],row['path']):row for row in cert['leaves']}
    assert len(records)==len(cert['leaves'])
    used=set()
    for root in range(len(outer)):
        stack=[(((F(0),F(0)),outer[root],outer[(root+1)%len(outer)]),'')]
        while stack:
            tri,path=stack.pop();key=(root,path)
            if key in records:
                row=records[key];ids=row['hull'];assert len(ids)>=3
                assert hull(ids,points)==ids
                assert all(d2(points[i],v)<=reception**2 for i in ids for v in tri)
                assert all(robust_contains([points[i] for i in ids],v,eta) for v in tri)
                used.add(key)
            else:
                assert len(path)<cert['maxdepth']
                a,b=split(tri);stack.append((b,path+'1'));stack.append((a,path+'0'))
    assert used==set(records)
    return len(used)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('output',nargs='?');parser.add_argument('--n',type=int,default=128);parser.add_argument('--maxdepth',type=int,default=30);parser.add_argument('--reception',default='998');parser.add_argument('--eta',default='0.1');parser.add_argument('--verify',action='store_true');a=parser.parse_args()
    raw=json.loads(Path(a.input).read_text(encoding='utf-8'),parse_float=Decimal)
    if a.verify:print('VERIFIED leaves',verify(raw))
    else:
        points=raw['points'] if isinstance(raw,dict) else raw
        cert=certify([tuple(map(F,p)) for p in points],a.n,a.maxdepth,F(a.reception),F(a.eta))
        if a.output:Path(a.output).write_text(json.dumps(cert,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in cert.items() if k not in ['points','leaves','unresolved']},indent=2))
