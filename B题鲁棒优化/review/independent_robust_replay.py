"""Independent exact replay: no import of robust_cover_certificate.py.

Partition coverage is checked using prefix-free binary paths plus exact Kraft
equality for every fan root, separately from the producer's DFS replay.
"""
from fractions import Fraction as Q
from functools import lru_cache
from pathlib import Path
import json,sys
if not __debug__:raise RuntimeError('Certificate checking requires Python assertions; do not use -O.')

def vec(a,b):return(b[0]-a[0],b[1]-a[1])
def scalar(a,b):return a[0]*b[0]+a[1]*b[1]
def determinant(a,b):return a[0]*b[1]-a[1]*b[0]
def squared(a,b):u=vec(a,b);return scalar(u,u)

def replay(data):
    assert data['status']=='CERTIFIED'
    rho=Q(data['reception']);eta=Q(data['perturbation_radius'])
    assert data['radius']==1800 and eta>0 and rho>0 and rho+eta<=1000
    sites=[tuple(map(Q,p)) for p in data['points']]
    n=data['tangent_quadrant_subdivisions'];assert isinstance(n,int) and n>0
    normal=[]
    for quadrant in range(4):
        for k in range(n):
            denominator=n*n+k*k
            x,y=Q(n*n-k*k,denominator),Q(2*n*k,denominator)
            u=[(x,y),(-y,x),(-x,-y),(y,-x)][quadrant]
            assert scalar(u,u)==1
            normal.append(u)
    boundary=[]
    for j,a in enumerate(normal):
        b=normal[(j+1)%len(normal)];d=determinant(a,b);assert d>0
        p=(Q(1800)*(b[1]-a[1])/d,Q(1800)*(a[0]-b[0])/d)
        assert scalar(a,p)==1800 and scalar(b,p)==1800
        boundary.append(p)
    paths=[[] for _ in boundary]
    for row in data['leaves']:
        root,path=row['root'],row['path']
        assert 0<=root<len(boundary) and set(path)<=set('01') and len(path)<=data['maxdepth']
        paths[root].append(path)
    for rootpaths in paths:
        assert rootpaths
        ordered=sorted(rootpaths)
        assert all(not b.startswith(a) for a,b in zip(ordered,ordered[1:]))
        assert sum((Q(1,2**len(p)) for p in ordered),Q(0))==1
    @lru_cache(None)
    def triangle(root,path):
        if not path:return((Q(0),Q(0)),boundary[root],boundary[(root+1)%len(boundary)])
        parent=triangle(root,path[:-1])
        lengths=[squared(parent[j],parent[(j+1)%3]) for j in range(3)]
        j=lengths.index(max(lengths))
        a,b,c=parent[j],parent[(j+1)%3],parent[(j+2)%3]
        midpoint=((a[0]+b[0])/2,(a[1]+b[1])/2)
        return(a,midpoint,c) if path[-1]=='0' else(midpoint,b,c)
    minimum=None
    for row in data['leaves']:
        ids=row['hull'];assert len(ids)>=3 and len(set(ids))==len(ids)
        polygon=[sites[i] for i in ids]
        assert len(set(polygon))==len(polygon)
        assert sum(determinant(a,polygon[(j+1)%len(polygon)]) for j,a in enumerate(polygon))>0
        vertices=triangle(row['root'],row['path'])
        assert all(squared(s,z)<=rho*rho for s in polygon for z in vertices)
        for j,a in enumerate(polygon):
            b=polygon[(j+1)%len(polygon)];edge=vec(a,b);edge2=scalar(edge,edge)
            assert all(determinant(edge,vec(a,s))>=0 for s in polygon)
            for z in vertices:
                signed=determinant(edge,vec(a,z))
                assert signed>0 and signed*signed>=eta*eta*edge2
                clearance2=signed*signed/edge2
                minimum=clearance2 if minimum is None else min(minimum,clearance2)
    assert len(data['leaves'])==data['leaf_count']
    return {'status':'INDEPENDENTLY_VERIFIED','leaf_count':len(data['leaves']),
            'eta_m':str(eta),'reception_m':str(rho),'minimum_hull_clearance_squared':str(minimum)}

if __name__=='__main__':
    data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    result=replay(data)
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
