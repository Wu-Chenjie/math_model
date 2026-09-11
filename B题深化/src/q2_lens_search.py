"""Floating exploratory search; exact proof is in q2_full_domain_certificate.py."""
import math
import json
from scipy.optimize import minimize, minimize_scalar
e=math.radians(1.005)
c,s=math.cos(e),math.sin(e)
k,h,z,l=math.sin(3*e),math.cos(3*e),math.sin(2*e),math.sin(4*e)
def t(q):
    a,b=q
    return (1500*(k*a+h*b)-z*(a*a+b*b))/(1500*l+h*b-k*a)
def lower(q):
    v=t(q)
    return math.sqrt(1500**2+v*v-3000*v*math.cos(2*e))/2
def cons(q):
    a,b=q;d=a*c-b*s;v=a*a+b*b
    return [2000*d-v,999975+10*d-v]
if __name__=='__main__':
    res=minimize(lambda q:-t(q),[900,440],bounds=[(0,1005),(27,1000)],constraints=[{'type':'ineq','fun':cons}],method='SLSQP',options={'ftol':1e-11,'maxiter':1000})
    print(json.dumps({'q':res.x.tolist(),'t':t(res.x),'lower':lower(res.x),'constraints':cons(res.x),'success':bool(res.success),'message':res.message},indent=2))
