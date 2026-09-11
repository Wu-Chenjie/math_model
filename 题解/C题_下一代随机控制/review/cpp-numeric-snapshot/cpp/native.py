"""Checked NumPy/CSR transport into C++ kernels; no policy or solver changes."""
from pathlib import Path
import ctypes as C
import hashlib,json
import numpy as np
from scipy.sparse import csr_matrix
from nextgen_scenarios import weighted_quantile
from control import EMIN, EMAX, MarkovDP as ReferenceMarkovDP
from nextgen_control import terminal_values, minimize_action
R=Path(__file__).resolve().parent
EXPECTED_ADAPTERS={'src/control.py','src/nextgen_control.py','cpp/generate_adapters.py','cpp/native_planner.py','cpp/native_enhanced.py','cpp/native_feedback.py'}
def validate_artifacts():
    sources=json.loads((R/'adapter-sources.json').read_text())
    if set(sources)!=EXPECTED_ADAPTERS:raise RuntimeError('Incomplete adapter-source manifest')
    for relative, expected in sources.items():
        if hashlib.sha256((R.parent/relative).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Stale generated adapter: '+relative)
    meta=json.loads((R/'build.json').read_text())
    for file,key in [('kernels.cpp','source_sha256'),('libmicrogrid.dylib','binary_sha256')]:
        digest=hashlib.sha256((R/file).read_bytes()).hexdigest()
        if digest!=meta[key]:raise RuntimeError('Native binary/source mismatch: '+file)
        if 'LOADED_HASHES' in globals() and LOADED_HASHES[file]!=digest:raise RuntimeError('Loaded native library changed; start a new process')
validate_artifacts()
LOADED_HASHES={file:hashlib.sha256((R/file).read_bytes()).hexdigest() for file in ['kernels.cpp','libmicrogrid.dylib']}
lib=C.CDLL(str(R/'libmicrogrid.dylib'))
D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
I=np.ctypeslib.ndpointer(dtype=np.int64,flags='C_CONTIGUOUS')
lib.mg_convolution.argtypes=[D,D,C.c_int,C.c_double,C.c_double,D];lib.mg_convolution.restype=C.c_int
lib.mg_markov.argtypes=[D,D,D,D,I,D,D]+[C.c_int]*5+[D,D,D];lib.mg_markov.restype=C.c_int
lib.mg_expression.argtypes=[C.c_int]*4+[C.c_int64,C.c_int,C.c_int,D,D,D,C.c_int,I,I,D,D]
lib.mg_expression.restype=C.c_int64

def array(x):
    result=np.ascontiguousarray(x,dtype=np.float64)
    if not np.isfinite(result).all():raise ValueError('Native kernel input must be finite')
    return result

def inf_convolution(grid,v,a,p):
    grid=array(grid);v=array(v)
    if grid.ndim!=1 or v.shape!=grid.shape or len(grid)<2 or np.any(np.diff(grid)<=0):raise ValueError('Invalid inventory grid/value')
    if not np.isfinite(a) or not np.isfinite(p) or p<0:raise ValueError('Invalid net demand/price')
    out=np.empty_like(grid)
    if lib.mg_convolution(grid,v,len(grid),a,p,out):raise RuntimeError('Native convolution failed')
    return out

def expression(which,S,T,F,asof,N,intercept,gain,energy,previous,base):
    fields=(S,T,F,asof,N,intercept,gain)
    if any(not isinstance(x,(int,np.integer)) or isinstance(x,(bool,np.bool_)) for x in fields):raise ValueError('Expression dimensions/indices must be integers')
    S,T,F,asof,N,intercept,gain=map(int,fields)
    if which not in ('Q','R','E') or min(S,T,F,N)<=0 or min(asof,intercept,gain)<0:raise ValueError('Expression domain violation')
    if max(S,T,F,N,intercept,gain,S*T*(F+1))>=2**31 or asof+T>=2**63:raise ValueError('Expression index capacity exceeded')
    groups=(asof+T-1)//(144 if which=='Q' else 36)-asof//(144 if which=='Q' else 36)+1
    if intercept+T>N or gain+F*groups>N:raise ValueError('Expression column outside LP bounds')
    energy=array(energy);previous=array(previous)
    if energy.shape!=(S,T,F) or previous.shape!=energy.shape:raise ValueError('Feature shape mismatch')
    b=np.zeros(T) if base is None else array(base)
    if b.ndim!=1 or len(b)<min(T,144-asof%144):raise ValueError('Base contract too short')
    indptr=np.empty(S*T+1,np.int64);indices=np.empty(S*T*(F+1),np.int64);values=np.empty(len(indices));constant=np.empty(S*T)
    n=lib.mg_expression({'Q':0,'R':1,'E':2}[which],S,T,F,asof,intercept,gain,energy,previous,b,int(base is not None),indptr,indices,values,constant)
    if n<0 or n>len(values):raise RuntimeError('Native expression capacity exceeded')
    return csr_matrix((values[:n],indices[:n],indptr),shape=(S*T,N)),constant

class MarkovDP:
    action=ReferenceMarkovDP.action
    def __init__(self,net,prices,q,tail_price,grid_size=321,terminal=None,tail_cuts=None):
        net=array(net);self.cuts=np.quantile(net,[1/3,2/3],axis=0).T
        labels=(net>self.cuts[:,0]).astype(int)+(net>self.cuts[:,1]).astype(int)
        _build(self,net,prices,q,np.full(len(net),1/len(net)),labels,tail_price,grid_size,3,terminal,tail_cuts,True)

class WeightedMarkovDP:
    def __init__(self,net,prices,q,weights,tail_price,grid_size=321,bins=3,terminal=None,tail_cuts=None):
        self.legacy=None;net=array(net);weights=array(weights)
        if bins==3 and np.allclose(weights,1/len(weights),rtol=0,atol=1e-15):
            self.legacy=MarkovDP(net,prices,q,tail_price,grid_size,terminal,tail_cuts);return
        self.cuts=np.array([weighted_quantile(net[:,j],np.arange(1,bins)/bins,weights) for j in range(net.shape[1])])
        labels=np.sum(net[:,:,None]>self.cuts[None],axis=2)
        _build(self,net,prices,q,weights,labels,tail_price,grid_size,bins,terminal,tail_cuts,False)
    def action(self,j,E,net,q,state=None):
        if self.legacy is not None:return self.legacy.action(j,E,net,q)
        k=int(np.sum(net>self.cuts[j]));return minimize_action(self.grid,self.future[j,k],E,net-q,self.price[j,k])

def _build(obj,net,prices,q,weights,labels,tail_price,G,B,terminal,cuts,legacy):
    net=array(net);prices=array(prices);q=array(q);weights=array(weights)
    if net.ndim!=2:raise ValueError('Expected scenario/time matrix')
    S,T=net.shape;labels=np.ascontiguousarray(labels,dtype=np.int64)
    if prices.shape!=net.shape or q.shape!=(T,) or weights.shape!=(S,) or labels.shape!=net.shape:raise ValueError('Native DP shape mismatch')
    if S<1 or T<1 or G<2 or B<1 or np.any(weights<=0) or np.any(prices<0) or np.any(labels<0) or np.any(labels>=B):raise ValueError('Native DP domain violation')
    obj.grid=np.linspace(EMIN,EMAX,G);obj.T=T
    obj.future=np.empty((T,B,G));obj.price=np.empty((T,B));obj.initial_values=np.empty((B,G))
    v=array(terminal_values(obj.grid,tail_price,terminal,cuts))
    status=lib.mg_markov(net,prices,q,weights,labels,obj.grid,v,S,T,B,G,int(legacy),obj.future,obj.price,obj.initial_values)
    if status:raise RuntimeError('Native Markov recursion failed')
