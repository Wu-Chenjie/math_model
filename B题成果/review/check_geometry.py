"""Independent deterministic checks; stdlib only, no simulator truth access."""
import json
import math
from pathlib import Path


def sub(a, b): return (a[0]-b[0], a[1]-b[1])
def cross(a, b): return a[0]*b[1]-a[1]*b[0]
def dot(a, b): return a[0]*b[0]+a[1]*b[1]
def norm(a): return math.hypot(*a)


def q1():
    side, extension = 40.0, 1000.0
    vertices = [(0., 0.), (side, 0.), (side/2, side*math.sqrt(3)/2)]
    observations, constraints = [], []
    centroid = tuple(sum(v[k] for v in vertices)/3 for k in (0, 1))
    for j in range(3):
        a, b = vertices[j], vertices[(j+1)%3]
        d = tuple((b[k]-a[k])/side for k in (0, 1))
        s = tuple(a[k]-extension*d[k] for k in (0, 1))
        theta = 120*j+1.
        bearing = math.degrees(math.atan2(centroid[1]-s[1], centroid[0]-s[0]))%360
        err = (theta-bearing+180)%360-180
        observations.append(dict(position=s, svd_deg=theta, true_bearing=bearing,
                                 physical_error_deg=err, source_distance=norm(sub(centroid,s))))
        for angle, sign in [(theta-1, 1), (theta+1, -1)]:
            t=math.radians(angle)
            normal=(-sign*math.sin(t), sign*math.cos(t))
            constraints.append((normal, dot(normal,s)))
    # Enumerate all six line-pair intersections; no artificial clipping box.
    poly=[]
    for j, (a,c) in enumerate(constraints):
        for b,d in constraints[j+1:]:
            det=cross(a,b)
            if abs(det)<1e-12: continue
            p=((c*b[1]-a[1]*d)/det,(a[0]*d-c*b[0])/det)
            if all(dot(n,p)>=v-1e-8 for n,v in constraints):
                if all(norm(sub(p,v))>1e-7 for v in poly): poly.append(p)
    assert len(poly)==3
    assert all(min(norm(sub(p,v)) for v in vertices)<1e-7 for p in poly)
    assert all(abs(o['physical_error_deg'])<=1 for o in observations)
    diameter=max(norm(sub(a,b)) for a in poly for b in poly)
    return dict(observations=observations, true_source=centroid, reconstructed_vertices=poly,
                diameter=diameter, mec_radius=side/math.sqrt(3),
                diameter_circle_radius=diameter/2,
                min_extension_for_triangle_containment=side*math.sqrt(3)/2/math.tan(math.radians(2))-side/2)


def q2(eps_deg):
    e=math.radians(eps_deg)
    candidates=[]
    for r in (5.,1500.):
        for a in (650.,850.):
            for b in (200.,400.):
                dsq=a*a+b*b+r*r-2*r*(a*math.cos(e)-b*math.sin(e))
                candidates.append((math.sqrt(dsq),r,a,b,-eps_deg))
    maximum=max(candidates)
    return dict(eps_deg=eps_deg,max_distance=maximum[0],maximizer=dict(zip(['r','a','b','phi_deg'],maximum[1:])),
                exact_method='convex endpoint reduction in r,a,abs(b); angular worst endpoint opposite b')


def segment_distance_to_origin(a,b):
    d=sub(b,a)
    t=max(0.,min(1.,-dot(a,d)/dot(d,d)))
    return norm((a[0]+t*d[0],a[1]+t*d[1]))


def triangle_distance_to_origin(vs):
    cs=[cross(sub(vs[(k+1)%3],vs[k]),(-vs[k][0],-vs[k][1])) for k in range(3)]
    if min(cs)>=-1e-9 or max(cs)<=1e-9: return 0.
    return min(segment_distance_to_origin(vs[k],vs[(k+1)%3]) for k in range(3))


def triangular_grid(h):
    def xy(ij):
        i,j=ij
        return (h*(i+j/2),h*math.sqrt(3)*j/2)
    retained=set(); cells=0
    # More than enough for |x|,|y|<=1800+h for requested h>=900.
    for i in range(-8,9):
        for j in range(-8,9):
            for cell in (((i,j),(i+1,j),(i,j+1)),((i+1,j),(i+1,j+1),(i,j+1))):
                if triangle_distance_to_origin([xy(v) for v in cell])<=1800+1e-8:
                    retained.update(cell); cells+=1
    assert all(abs(i)<8 and abs(j)<8 for i,j in retained)
    return dict(h=h, intersecting_triangles=cells,point_count=len(retained),
                outermost_radius=max(norm(xy(v)) for v in retained),
                points=[xy(v) for v in sorted(retained)])


def square_grid(h=600):
    retained=set(); cells=0
    for i in range(-8,9):
        for j in range(-8,9):
            dx=max(i*h,0,-(i+1)*h);dy=max(j*h,0,-(j+1)*h)
            if math.hypot(dx,dy)<=1800+1e-8:
                retained.update(((i,j),(i+1,j),(i,j+1),(i+1,j+1)));cells+=1
    return dict(h=h,intersecting_squares=cells,point_count=len(retained),
                outermost_radius=max(h*norm(v) for v in retained))


def fallback():
    e=math.radians(1.005)
    half_width=1500*math.sin(e)
    dx=30.; dy=half_width
    cover_radius=math.hypot(dx/2,dy/2)
    points=[]
    for i in range(50):
        ys=(-dy/2,dy/2) if i%2==0 else (dy/2,-dy/2)
        points.extend(((dx*(i+.5),y) for y in ys))
    path=norm(points[0])+sum(norm(sub(a,b)) for a,b in zip(points,points[1:]))
    bound=path/5+99*3+5
    assert cover_radius<20
    return dict(epsilon_deg=1.005,rectangle=[0,1500,-half_width,half_width],
                columns=50,rows=2,clear_actions=100,cell_cover_radius=cover_radius,
                path_from_first_measurement=path,virtual_seconds_after_first_measurement=bound,
                failed_clear_max=99,successful_clear=1,
                note='If current position is p, add distance(p, first_measurement)/5 to this bound.')


def implemented_policy_bound():
    # Bounds match src/policy.hpp, not the separate 100-action construction.
    e=math.radians(1.005)
    r_polygon=1800/math.cos(math.pi/64)
    grid_radius=950*math.sqrt(7)
    first_second_radius=grid_radius+math.hypot(750,300)
    coordinate_radius=max(first_second_radius,math.sqrt(2)*r_polygon,r_polygon+50)
    safe_radius=math.ceil(coordinate_radius)
    width,height=1500.,3000*math.tan(e)
    nx,ny=math.ceil(width/28),math.ceil(height/28)
    fallback_clears=nx*ny
    internal_fallback_path=(fallback_clears-1)*28
    sources,grid_points=16,31
    measures=grid_points*20+sources*(2+3*2)
    clears=sources*(3+fallback_clears)
    coarse_segments=grid_points+sources*(2+3*3+1)
    travel=coarse_segments*2*safe_radius+sources*internal_fallback_path
    virtual=travel/5+6*measures+3*clears+2*sources
    assert (nx,ny)==(54,2)
    assert coordinate_radius<safe_radius
    assert virtual<360000
    return dict(polygon_radius=r_polygon,grid_radius=grid_radius,
                second_candidate_max_radius=first_second_radius,
                fallback_point_max_radius=math.sqrt(2)*r_polygon,
                universal_position_radius_raw=coordinate_radius,universal_position_radius_safe=safe_radius,
                first_rectangle_width=width,first_rectangle_height=height,
                fallback_columns=nx,fallback_rows=ny,fallback_clears_per_source=fallback_clears,
                fallback_cell_cover_radius=28/math.sqrt(2),
                fallback_internal_path_per_source=internal_fallback_path,
                max_measure_actions=measures,max_clear_actions=clears,
                max_total_actions_including_enter_exit=measures+clears+2,
                max_channel_switches=measures,coarse_movement_segments=coarse_segments,
                path_upper_bound=travel,virtual_time_upper_bound=virtual,
                virtual_hours_upper_bound=virtual/3600,virtual_budget_margin=360000-virtual,
                real_time_condition='Completion requires accepted serialized requests before the actual real deadline.')


def main():
    result=dict(q1=q1(),q2=[q2(1.),q2(1.005)],
                q3=dict(inner_boundary=1200/math.sqrt(3),
                        covering_radius=math.sqrt(1800**2+1200**2-2*1800*1200*math.cos(math.pi/6))),
                q4=dict(triangular=[triangular_grid(h) for h in (900,950,990)],square=square_grid()),
                fallback=fallback(),implemented_policy_bound=implemented_policy_bound())
    dest=Path(__file__).with_name('geometry_results.json')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({**result,'q4':{'triangular':[{k:v for k,v in a.items() if k!='points'} for a in result['q4']['triangular']],
                                             'square':result['q4']['square']}},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
