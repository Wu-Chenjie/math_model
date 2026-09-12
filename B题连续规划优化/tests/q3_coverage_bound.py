from fractions import Fraction as F
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sqrt3lo=F('1.7320508075688772935');sqrt3hi=F('1.7320508075688772936')
assert sqrt3lo**2<3<sqrt3hi**2
R=F(1800);reception=F('999.6');a=F(1124)
# Radius r <= reception is covered by the origin. In every angular sector
# |delta| <=30 degrees, squared distance to its ring point is convex in r.
# Its maximum on [reception,1800] is at an endpoint.
boundary=R*R+a*a-R*a*sqrt3lo
inner=reception*reception+a*a-reception*a*sqrt3lo
assert max(boundary,inner)<reception**2
points=json.loads((root/'results/q3_production_points.json').read_text())
assert len(points)==7
ideal=[(F(0),F(0)),(a,F(0)),(a/2,a*sqrt3lo/2),(-a/2,a*sqrt3lo/2),(-a,F(0)),(-a/2,-a*sqrt3lo/2),(a/2,-a*sqrt3lo/2)]
for actual,reference in zip(points,ideal):
    error=sum((F.from_float(float(x))-y)**2 for x,y in zip(actual,reference))
    assert error<F('0.0000000001')**2
assert F('0.0000000001')+a*(sqrt3hi-sqrt3lo)/2<F('0.000000001')
result={'ring_radius':1124,'certified_ideal_cover_radius':'999.6','boundary_squared_upper':str(boundary),'inner_squared_upper':str(inner),'sqrt3_interval':[str(sqrt3lo),str(sqrt3hi)],'coordinate_perturbation_allowance_m':'0.4','scope':'ideal sixfold ring + origin; implementation floating coordinates must be within 0.4m'}
result['production_binary64_error_bound_m']='0.000000001'
(root/'results/q3_coverage_bound.json').write_text(json.dumps(result,indent=2))
print('PASS rational radial/angular proof: 1124m seven-point ring covers the 1800m disk within 999.6m')
