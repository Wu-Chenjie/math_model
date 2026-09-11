"""Independent fourth-round raw-data audit, without analysis-module imports."""
from pathlib import Path
import csv,json,math,itertools
from collections import defaultdict,Counter
from statistics import mean,stdev
from scipy.stats import t

ROOT=Path(__file__).resolve().parents[1]
S=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
out={}
def read(name):return list(csv.DictReader((ROOT/f'results/{name}.csv').open()))
def stats(d):
    a=mean(d);h=t.ppf(.975,len(d)-1)*stdev(d)/math.sqrt(len(d))
    return {'mean':a,'ci95':[a-h,a+h]}

for name,total,methods in [('iid',2400,set(range(6))),('stratified',6480,{0,5})]:
    rows=read(name);assert len(rows)==total
    pairs=defaultdict(dict);residual=0
    for r in rows:
        p=int(r['problem']);key=(p,int(r['seed']));m=int(r['method'])
        assert m not in pairs[key];pairs[key][m]=r
        assert r['n']==r['cleared']
        assert r['certificate'] in ('upper_bound_16','seven_point_per_channel','convex_mesh_per_channel')
        val=float(r['move_m'])/5+int(r['switches'])+5*int(r['measures'])+3*int(r['miss'])+5*int(r['cleared'])
        residual=max(residual,abs(val-float(r['time_s'])))
        assert abs(val-float(r['time_s']))<.001
    for key,ms in pairs.items():
        assert set(ms)==methods
        fields=['problem','seed','n']+(['case_id','nd','nb','geometry','radius','error','outward','eigen_ratio']if name=='stratified'else[])
        assert all(len({r[f]for r in ms.values()})==1 for f in fields)
    if name=='iid':assert set(pairs)==set(itertools.product((3,4),range(510001,510201)))
    else:
        assert {int(ms[0]['case_id'])for ms in pairs.values()}==set(range(3240))
        assert all(int(ms[0]['seed'])==710001+int(ms[0]['case_id'])for ms in pairs.values())
        cells=defaultdict(list)
        for ms in pairs.values():cells[tuple(int(ms[0][f])for f in ['problem','n','nd','nb','geometry'])].append(ms)
        assert len(cells)==108
        nuisance=Counter(itertools.product((1000,1250,1500),range(5),range(2)))
        for cell,ps in cells.items():
            assert len(ps)==30
            assert Counter(tuple(int(x[0][f])for f in ['radius','error','outward'])for x in ps)==nuisance
        neg=[]
        for cell,ps in cells.items():
            ds=[float(x[0]['time_s'])-float(x[5]['time_s'])for x in ps]
            if mean(ds)<-1e-6:neg.append({'cell':cell,**stats(ds)})
        assert len(neg)==5
        assert {x['cell']for x in neg}=={tuple(x[f]for f in ['problem','n','nd','nb','geometry'])for x in S['negative_cells']}
        for row in neg:
            target=next(x for x in S['negative_cells']if tuple(x[f]for f in ['problem','n','nd','nb','geometry'])==row['cell'])
            assert abs(row['mean']-target['saving']['mean'])<1e-7
            assert max(abs(a-b)for a,b in zip(row['ci95'],target['saving']['ci95']))<1e-7
        out['negative_cells']=neg
    group={}
    for p in (3,4):
        ps=[v for k,v in pairs.items()if k[0]==p]
        n_expected=200 if name=='iid' else (810 if p==3 else 2430)
        assert len(ps)==n_expected
        base=[float(x[0]['time_s'])for x in ps]
        group[p]={}
        for m in sorted(methods):
            x=[float(v[m]['time_s'])for v in ps];d=[a-b for a,b in zip(base,x)]
            val={'mean_time':mean(x),'saving_percent':100*mean(d)/mean(base),'saving':stats(d),
                 'wins':sum(a>1e-6 for a in d),'losses':sum(a< -1e-6 for a in d)}
            if name=='iid':
                target=S['iid'][str(p)][str(m)]
                assert abs(val['mean_time']-target['time_s']['mean'])<1e-7
                assert abs(val['saving_percent']-target['saving_percent'])<1e-7
                for k in ['plans','exact_plans','nonlocal_plans']:assert sum(int(v[m][k])for v in ps)==target[k]
                assert max(float(v[m]['max_relative_gap'])for v in ps)==target['max_relative_gap']
                assert max(float(v[m]['max_route_gap_m'])for v in ps)==target['max_absolute_gap_m']
            elif m==5:
                target=S['controlled'][str(p)]
                assert abs(val['saving_percent']-target['saving_percent'])<1e-7
                assert max(abs(a-b)for a,b in zip(val['saving']['ci95'],target['saving_s']['ci95']))<1e-7
            group[p][m]=val
    out[name]={'rows':total,'max_accounting_residual':residual,'groups':group}

h=read('hardware');assert len(h)==320
assert {(int(r['problem']),int(r['seed']),int(r['disturbance']),int(r['aware']))for r in h}==set(itertools.product((3,4),range(610001,610021),range(4),range(2)))
aware=[r for r in h if r['aware']=='1'];nominal=[r for r in h if r['aware']=='0']
assert all(r['status']=='ok'and r['cleared']==r['total']for r in aware)
assert all(r['status']=='diagnostic_interruption'for r in nominal)
assert Counter(r['reason']for r in nominal)==Counter({'truth excluded from conservative polygon':156,'empty feasible region':4})
out['hardware']={'aware_complete':len(aware),'nominal_diagnostics':dict(Counter(r['reason']for r in nominal))}
eta=.4;step=min(28,math.sqrt(2)*(20-eta)-1e-6);width=1500+2*eta;height=2*(1500*math.sin(math.radians(1.005))+eta)
out['robust_budget']={'grid_side':step,'width':width,'height':height,'grid_count':math.ceil(width/step)*math.ceil(height/step),
  'nominal_length':213*5344+16*109*28,'actual_length':1187104+2*eta*(564+1808),'time':(1187104+2*eta*(564+1808))/5+6*564+3*1808+32}
assert out['robust_budget']['grid_count']==110
(ROOT/'review/fourth_scoring_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'iid_M5':{p:out['iid']['groups'][p][5]for p in (3,4)},'controlled_M5':{p:out['stratified']['groups'][p][5]for p in (3,4)},'negative_cells':out['negative_cells'],'hardware':out['hardware'],'robust_budget':out['robust_budget']},ensure_ascii=False,indent=2))
