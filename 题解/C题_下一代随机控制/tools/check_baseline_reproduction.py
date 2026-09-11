#!/usr/bin/env python3
"""Strict read-only comparison of frozen outputs and a clean, executed rerun.

No optimization is run and no production module is imported. NPZ contents are
compared by key/shape/value, never by compressed-file hash. Exit 0=PASS,
1=FAIL, 2=PENDING. Missing evidence cannot produce PASS.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse, csv, hashlib, json, sys, time
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
KINDS = ('q2', 'q3', 'q4_2', 'q4_3')
ANNUAL = ('closed_baseline', 'cross_baseline', 'affine_mpc', 'markov_mpc', 'closed_affine')
# Tolerance is fixed before observing the rerun. No automatic tolerance widening.
ARRAY_ATOL, ARRAY_RTOL = 1e-6, 1e-11
JSON_ATOL, JSON_RTOL = 1e-5, 1e-11
PHYSICAL_ATOL, BILL_ATOL = 1e-5, 1e-4
IGNORED_KEYS = {'runtime_seconds', 'source_hashes', 'source_sha256', 'execution',
                'source_trajectory_sha256', 'source_metrics_sha256'}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())


class Audit:
    def __init__(self, frozen, rerun):
        self.frozen, self.rerun = frozen, rerun
        self.cases = []; self.ignored = Counter(); self.started = time.perf_counter()

    def add(self, name, status, **details):
        self.cases.append({'name': name, 'status': status, **details})

    def files(self, rel):
        a, b = self.frozen / rel, self.rerun / rel
        missing = [str(p) for p in (a, b) if not p.is_file()]
        if missing:
            self.add(rel, 'PENDING', missing=missing); return None
        return a, b

    def compare_npz(self, rel):
        pair = self.files(rel)
        if pair is None: return
        details = {}; errors = []
        try:
            with np.load(pair[0], allow_pickle=False) as a, np.load(pair[1], allow_pickle=False) as b:
                if set(a.files) != set(b.files): errors.append('array key sets differ')
                for key in sorted(set(a.files) & set(b.files)):
                    x, y = a[key], b[key]
                    if x.shape != y.shape:
                        errors.append(f'{key}: shape mismatch {x.shape}/{y.shape}'); continue
                    if x.dtype.kind != y.dtype.kind:
                        errors.append(f'{key}: dtype-kind mismatch {x.dtype}/{y.dtype}'); continue
                    if x.dtype.kind in 'fc':
                        # Identical NaN positions are allowed for unused release records only.
                        valid_nan = key == 'releases'
                        finite = np.isfinite(x) & np.isfinite(y)
                        patterns = np.array_equal(np.isnan(x), np.isnan(y)) and np.array_equal(np.isinf(x), np.isinf(y))
                        legal = not np.isinf(x).any() and not np.isinf(y).any() and (valid_nan or not np.isnan(x).any())
                        same = np.isclose(x, y, atol=ARRAY_ATOL, rtol=ARRAY_RTOL, equal_nan=valid_nan)
                        ok = bool(patterns and legal and same.all())
                        diff = np.abs(x[finite] - y[finite]); max_abs = float(diff.max(initial=0))
                        bad = int(np.count_nonzero(~same))
                        details[key] = {'shape':list(x.shape), 'max_abs_difference':max_abs, 'different_elements':bad, 'nonfinite_pattern_equal':patterns}
                        if not ok: errors.append(f'{key}: {bad} differing elements or illegal nonfinite value')
                    else:
                        ok = bool(np.array_equal(x, y)); details[key] = {'shape':list(x.shape), 'exact_equal':ok}
                        if not ok: errors.append(f'{key}: nonfloating values differ')
        except Exception as exc: errors.append(f'{type(exc).__name__}: {exc}')
        self.add(rel, 'FAIL' if errors else 'PASS', arrays=details, errors=errors,
                 frozen_sha256=sha(pair[0]), rerun_sha256=sha(pair[1]))

    def normalize(self, o, path=''):
        if isinstance(o, dict):
            ans = {}
            for k, v in o.items():
                if k in IGNORED_KEYS:
                    self.ignored[f'{path}/{k}'] += 1; continue
                ans[k] = self.normalize(v, f'{path}/{k}')
            # v1 omitted incoming inventory, but actual state and documented default were6000.
            if path.endswith('/configuration') and 'start_day' in ans and 'initial' not in ans:
                ans['initial'] = 6000.
            if 'as_of' in ans and ans.get('tail_model_cutoff') is None and ans.get('tail_cut_count') == 0 and 'tail_model_days' not in ans:
                ans['tail_model_days'] = None
            return ans
        if isinstance(o, list):
            out = [self.normalize(v, f'{path}/*') for v in o]
            if path.endswith('/results') and out and all(isinstance(v,dict) and 'kind' in v and 'candidate' in v for v in out):
                out.sort(key=lambda v:(v['kind'],v['candidate']))
            return out
        return o

    def compare_json(self, rel):
        pair = self.files(rel)
        if pair is None: return
        errors=[]; numeric_count=0; max_abs=0.
        def walk(a,b,path):
            nonlocal numeric_count,max_abs
            if isinstance(a,dict) and isinstance(b,dict):
                if set(a)!=set(b): errors.append(f'{path}: keys differ {sorted(set(a)^set(b))}')
                for k in sorted(set(a)&set(b)):walk(a[k],b[k],f'{path}/{k}')
            elif isinstance(a,list) and isinstance(b,list):
                if len(a)!=len(b):errors.append(f'{path}: list lengths {len(a)}/{len(b)}')
                for i,(x,y) in enumerate(zip(a,b)):walk(x,y,f'{path}/{i}')
            elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
                numeric_count+=1; diff=abs(a-b);max_abs=max(max_abs,diff)
                if not np.isfinite(a) or not np.isfinite(b) or diff>JSON_ATOL+JSON_RTOL*abs(a):
                    errors.append(f'{path}: {a!r} != {b!r}')
            elif type(a)!=type(b) or a!=b:errors.append(f'{path}: {str(a)[:120]!r} != {str(b)[:120]!r}')
        try:walk(self.normalize(read(pair[0])),self.normalize(read(pair[1])),'')
        except Exception as exc:errors.append(f'{type(exc).__name__}: {exc}')
        self.add(rel,'FAIL' if errors else 'PASS',numeric_fields=numeric_count,max_abs_numeric_difference=max_abs,
                 error_count=len(errors),errors=errors[:50],frozen_sha256=sha(pair[0]),rerun_sha256=sha(pair[1]))

    def compare_csv(self, rel):
        pair=self.files(rel)
        if pair is None:return
        errors=[];maximum=0.;cells=0
        try:
            with pair[0].open(encoding='utf-8-sig',newline='') as fa,pair[1].open(encoding='utf-8-sig',newline='') as fb:
                a=list(csv.reader(fa));b=list(csv.reader(fb))
            if len(a)!=len(b):errors.append('row count mismatch')
            for i,(ra,rb) in enumerate(zip(a,b)):
                if len(ra)!=len(rb):errors.append(f'row {i}: width mismatch')
                for j,(x,y) in enumerate(zip(ra,rb)):
                    cells+=1
                    if x==y:continue
                    try:
                        xx,yy=float(x),float(y);diff=abs(xx-yy);maximum=max(maximum,diff)
                        if not np.isfinite(xx) or not np.isfinite(yy) or diff>JSON_ATOL+JSON_RTOL*abs(xx):errors.append(f'row {i} column {j}: {x}/{y}')
                    except ValueError:errors.append(f'row {i} column {j}: text mismatch')
        except Exception as exc:errors.append(str(exc))
        self.add(rel,'FAIL' if errors else 'PASS',cells=cells,max_numeric_difference=maximum,error_count=len(errors),errors=errors[:30])

    def independent_initialization(self):
        paths=[self.rerun/'artifacts'/p for p in ('data.npz','q1.npz','q1.json','january-warmup.npz','warmup.json')]
        if not all(p.is_file() for p in paths):
            self.add('independent:Q1_and_January','PENDING');return
        errors=[];checks={}
        def check(k,x,tol=PHYSICAL_ATOL):
            x=float(x);checks[k]=x
            if not np.isfinite(x) or x>tol:errors.append(k)
        try:
            d=dict(np.load(paths[0]));a=dict(np.load(paths[1]));m=read(paths[2]);w=dict(np.load(paths[3]));wm=read(paths[4])
            q,c,b,E=[a[k] for k in ('q','c','d','state')]
            n=(d['day_load']-d['day_pv'])/6
            check('q1_nonnegative',max(0.,-min(q.min(),c.min(),b.min())))
            check('q1_demand_coverage',max(0.,float((n-q+c-b).max())))
            check('q1_soc_recurrence',np.abs(np.diff(E)-.9*c+b/.9).max())
            check('q1_endpoints',max(abs(E[0]-6000),abs(E[-1]-6000)))
            check('q1_capacity',max(0.,1200-E.min(),E.max()-10800))
            check('q1_power',max(0.,6*c.max()-5000,6*b.max()-5000))
            check('q1_single_direction',np.minimum(c,b).max())
            check('q1_bill',abs(d['day_price']@q-m['expected_cost']),BILL_ATOL)
            n=(d['load'][:31]-d['pv'][:31])/6
            check('january_bus',np.abs(w['r']+w['emergency']+w['d']-w['c']-w['spill']-n).max())
            check('january_hold6000',np.abs(w['state']-6000).max())
            check('january_no_contract_or_charge',max(np.abs(w[k]).max() for k in ('q','r','c','d')))
            check('january_emergency',np.abs(w['emergency']-np.maximum(n,0)).max())
            check('january_spill',np.abs(w['spill']-np.maximum(-n,0)).max())
            check('january_fixed_bill',abs(np.sum(5*d['day_price']*w['emergency'])-wm['fixed_price_cost']),BILL_ATOL)
            check('january_variable_bill',abs(np.sum(5*d['price'][:31]*w['emergency'])-wm['variable_price_cost']),BILL_ATOL)
        except Exception as exc:errors.append(str(exc))
        self.add('independent:Q1_and_January','FAIL' if errors else 'PASS',checks=checks,errors=errors)

    def independent_trajectory(self, stem):
        """Independent physical/bill recalculation; no production functions reused."""
        p=self.rerun/(stem+'.npz'); j=self.rerun/(stem+'.json'); data_path=self.rerun/'artifacts/data.npz'
        if not all(x.is_file() for x in (p,j,data_path)):
            self.add('independent:'+stem,'PENDING',reason='trajectory, metrics or data missing');return
        errors=[]; checks={}
        def residual(name, value, tolerance=PHYSICAL_ATOL):
            v=float(value); checks[name]=v
            if not np.isfinite(v) or v>tolerance:errors.append(f'{name}: {v} > {tolerance}')
        try:
            a=dict(np.load(p));d=dict(np.load(data_path));m=read(j)
            days=a['days']; E=a['state'];q=a['q'];r=a['r'];c=a['c'];b=a['d'];e=a['emergency'];sp=a['spill'];price=a['price']
            load=d['load'][days].copy();pv=d['pv'][days].copy()
            if m.get('validation_design',{}).get('stress'):load*=1.1;pv*=.8
            residual('bus_balance',np.max(np.abs(r+e+b-c-sp-(load-pv)/6)))
            residual('inventory_recurrence',np.max(np.abs(np.diff(E,axis=1)-.9*c+b/.9)))
            residual('capacity_violation',max(0.,1200-E.min(),E.max()-10800))
            residual('power_violation_kw',max(0.,6*c.max()-5000,6*b.max()-5000))
            residual('negative_energy',max(0.,-min(v.min() for v in (q,r,c,b,e,sp))))
            residual('simultaneous_charge_discharge',np.minimum(c,b).max())
            residual('midnight_jump',np.max(np.abs(E[1:,0]-E[:-1,-1]),initial=0))
            kind=m['kind'];variable=kind.startswith('q4');official=kind in ('q3','q4_3')
            residual('observed_scoring_price',np.max(np.abs(price-(d['price'][days] if variable else d['day_price']))),1e-12)
            fixed=stem.startswith('artifacts/global-terminal/')
            config=m['fixed_suffix_configuration'] if fixed else m['configuration']
            residual('initial_inventory',abs(E[0,0]-(6000 if fixed else config.get('initial',6000))))
            target=6000 if fixed or config.get('closed_daily') else config.get('final')
            if target is not None:residual('true_terminal',abs(E[-1,-1]-target))
            if config.get('closed_daily'):residual('daily_closure',np.abs(E[:,-1]-6000).max())
            if not np.array_equal(a['dates'],d['dates'][days]):errors.append('dates do not agree with data day indices')
            if not np.all(np.diff(days)==1):errors.append('nonconsecutive replay days')
            if not official:residual('no_adjustment_permission',np.abs(r-q).max())
            else:
                residual('first_six_hours_frozen',np.abs(r[:,:36]-q[:,:36]).max())
                rebuilt=q.copy()
                for issue in range(1,4):
                    vals=a['releases'][:,issue,issue*36:]
                    if not np.isfinite(vals).all():errors.append(f'missing revision {issue}')
                    rebuilt[:,issue*36:]=vals
                residual('release_reconstructs_r',np.abs(rebuilt-r).max())
            residual('original_q_release',np.abs(a['releases'][:,0]-q).max())
            parts={'planned_cost':price*q,'increase_cost':1.5*price*np.maximum(r-q,0),
                   'reduction_net_cost':-.5*price*np.maximum(q-r,0),'emergency_cost':5*price*e}
            parts['total_cost']=sum(parts.values())
            if fixed:
                residual('full_bill_total',abs(parts['total_cost'].sum()-m['fixed_total_cost']),BILL_ATOL)
                daily=m['fixed_suffix_daily'];slice_start=len(days)-len(daily)
            else:daily=m['daily'];slice_start=0
            for key,val in parts.items():
                if not fixed:residual('total:'+key,abs(val.sum()-m['totals'][key]),BILL_ATOL)
                residual('daily:'+key,np.max(np.abs(val.sum(1)[slice_start:]-[v[key] for v in daily])),BILL_ATOL)
            for key,val in [('emergency_energy',e),('spill_energy',sp)]:
                if not fixed:residual('total:'+key,abs(val.sum()-m['totals'][key]),BILL_ATOL)
                residual('daily:'+key,np.max(np.abs(val.sum(1)[slice_start:]-[v[key] for v in daily])),BILL_ATOL)
            for decision in m.get('decisions',m.get('fixed_suffix_decisions',[])):
                now,end=decision['as_of'],decision['end'];T=end-now
                if decision['latest_training_target_exclusive']>now:errors.append('recorded immature residual block')
                if any(h*144+now%144+T>now for h in decision['history_days']):errors.append('reconstructed immature residual block')
                if decision.get('tail_model_cutoff') is not None and decision['tail_model_cutoff']*144>now:errors.append('future SDDP training cutoff')
            # Claimed solver validations must also satisfy their own hard threshold.
            for k in ('lp_violation_max','lp_objective_recompute_gap'):
                v=m.get('validation',m.get('fixed_suffix_validation',{})).get(k)
                if v is not None:residual('solver:'+k,v)
        except Exception as exc:errors.append(f'{type(exc).__name__}: {exc}')
        self.add('independent:'+stem,'FAIL' if errors else 'PASS',checks=checks,errors=errors)

    def execution(self, rel, expected_count=None, expected_keys=None):
        p=self.rerun/rel
        if not p.is_file():self.add('execution:'+rel,'PENDING');return
        errors=[]
        try:
            obj=read(p);m=obj.get('execution',obj)
            if m.get('exit_code')!=0:errors.append('nonzero or missing recorded exit code')
            if expected_count is not None and len(obj.get('results',[]))!=expected_count:errors.append('wrong completed result count')
            if expected_keys is not None:
                actual={(x['kind'],x['candidate']) for x in obj.get('results',[])}
                if actual!=set(expected_keys):errors.append('completed candidate identities mismatch')
            frozen=read(PROJECT/'artifacts/baseline-freeze.json')
            if p.stat().st_mtime < datetime.fromisoformat(frozen['created']).timestamp():errors.append('execution record predates baseline freeze')
        except Exception as exc:errors.append(str(exc))
        self.add('execution:'+rel,'FAIL' if errors else 'PASS',errors=errors,sha256=sha(p))

    def run(self):
        freeze=read(PROJECT/'artifacts/baseline-freeze.json');errors=[]
        for rel,expected in freeze['file_hashes'].items():
            p=self.frozen/rel
            if not p.is_file() or sha(p)!=expected:errors.append(rel)
        self.add('frozen_snapshot_integrity','FAIL' if errors else 'PASS',errors=errors,files=len(freeze['file_hashes']))
        for folder in ('src','inputs','vendor'):
            errors=[];count=0
            for p in (self.frozen/folder).rglob('*'):
                if not p.is_file() or '__pycache__' in p.parts:continue
                rel=p.relative_to(self.frozen);q=self.rerun/rel;count+=1
                if not q.is_file() or sha(p)!=sha(q):errors.append(str(rel))
            self.add('unchanged:'+folder,'FAIL' if errors else 'PASS',files=count,errors=errors)
        self.compare_npz('artifacts/data.npz');self.compare_npz('artifacts/january-warmup.npz')
        for name in ('data-audit','warmup','forecast-selection','selection','q1'):
            self.compare_json('artifacts/'+name+'.json')
        self.compare_npz('artifacts/q1.npz');self.independent_initialization()
        groups={'annual':ANNUAL,'annual_sddp':('sddp_markov',),
                'calibrate':('cross_baseline','affine_mpc','markov_mpc'),
                'calibrate_closed':('closed_baseline','closed_affine'),
                'calibrate_sddp_v2':('sddp_mpc','sddp_markov'),
                'global-terminal':('affine_mpc','markov_mpc')}
        for group,candidates in groups.items():
            for kind in KINDS:
                for candidate in candidates:
                    stem=f'artifacts/{group}/{kind}_{candidate}'
                    self.compare_npz(stem+'.npz');self.compare_json(stem+'.json');self.independent_trajectory(stem)
        for p in sorted((self.frozen/'artifacts/experiments').glob('*.json')):
            stem=str(p.relative_to(self.frozen))[:-5]
            self.compare_npz(stem+'.npz');self.compare_json(stem+'.json');self.independent_trajectory(stem)
        for kind in KINDS:
            stem='artifacts/'+kind
            self.compare_npz(stem+'.npz');self.compare_json(stem+'.json');self.independent_trajectory(stem)
        for p in sorted((self.frozen/'artifacts/tails').glob('*.json')):self.compare_json(str(p.relative_to(self.frozen)))
        self.compare_json('artifacts/global-terminal.json')
        for name in ('workbook-payload','handoff-tables','summary','figure-data'):
            self.compare_json('artifacts/'+name+'.json')
        for p in sorted((self.frozen/'计算结果').glob('*.csv')):self.compare_csv(str(p.relative_to(self.frozen)))
        for phase,candidates in groups.items():
            if phase=='global-terminal':continue
            self.execution('artifacts/execution-'+phase+'.json',4*len(candidates),[(k,c) for k in KINDS for c in candidates])
        for phase,count in [('train',48),('train-D1',8),('train-D2',8),('experiments-short',15),('experiments-annual-releases',4)]:
            self.execution('artifacts/execution-'+phase+'.json',count)
        self.execution('artifacts/global-terminal.json',8)
        for phase in ('selection','finish','export'):self.execution('artifacts/execution-'+phase+'.json')
        p=self.rerun/'review/production-audit.json'
        if not p.exists():self.add('rerun_independent_production_audit','PENDING')
        else:
            m=read(p);ok=m.get('passed') is True and m.get('passed_cases')==36 and not m.get('pending_cases') and not m.get('failed_cases')
            self.add('rerun_independent_production_audit','PASS' if ok else 'FAIL',sha256=sha(p))
        p=self.rerun/'artifacts/workbook-validation.json'
        if not p.exists():self.add('rerun_workbook_readback','PENDING')
        else:
            m=read(p);checks=m.get('checks',[]);ok=len(checks)==5 and all(c.get('status')=='pass' and (self.rerun/c['file']).is_file() and sha(self.rerun/c['file'])==c['sha256'] for c in checks) and m.get('execution',{}).get('exit_code')==0
            self.add('rerun_workbook_readback','PASS' if ok else 'FAIL',sha256=sha(p))
        counts=Counter(v['status'] for v in self.cases)
        status='FAIL' if counts['FAIL'] else 'PENDING' if counts['PENDING'] else 'PASS'
        evidence_paths=[]
        for directory in [self.frozen,*[self.rerun/name for name in ('src','inputs','vendor','artifacts','计算结果','review')]]:
            evidence_paths.extend(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
        evidence_hashes={str(p.relative_to(PROJECT)) if p.is_relative_to(PROJECT) else str(Path('..')/p.relative_to(PROJECT.parent)):sha(p) for p in sorted(set(evidence_paths))}
        return {'schema_version':1,'status':status,'reviewer_id':'/root/upgrade_code_review','independent':True,
          'evidence_hashes':evidence_hashes,
          'frozen_root':str(self.frozen),'rerun_root':str(self.rerun),'counts':dict(counts),'cases':self.cases,
          'tolerances':{'array_atol':ARRAY_ATOL,'array_rtol':ARRAY_RTOL,'json_atol':JSON_ATOL,'json_rtol':JSON_RTOL,'physical_atol':PHYSICAL_ATOL,'bill_atol':BILL_ATOL},
          'scope':'Current accepted numerical results, arrays, training and validation. Historical pilot, 300iteration tails and superseded calibrate_sddp are archival, excluded explicitly. This is not authorization to adopt any upgraded model.',
          'normalization':'Only v1 omitted configuration.initial is filled with documented6000; non-SDDP omitted tail_model_days becomes null only when cutoff=null and cut_count=0. Actual initial states compared. Task completion order sorted only in keyed global-terminal results. Runtime/provenance hashes excluded from numerical equality and source/input integrity verified separately.',
          'ignored_nonnumerical_fields':dict(self.ignored),'execution':{'command':' '.join(sys.argv),'runtime_seconds':time.perf_counter()-self.started,'checker_sha256':sha(Path(__file__)),'created_utc':datetime.now(timezone.utc).isoformat()}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen',type=Path,default=PROJECT/'baseline_frozen')
    parser.add_argument('--rerun',type=Path,default=PROJECT.parent/'C题_下一代基线复现')
    parser.add_argument('--output',type=Path,default=PROJECT/'artifacts/baseline-reproduction-check.json')
    args=parser.parse_args();audit=Audit(args.frozen.resolve(),args.rerun.resolve());report=audit.run()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    bad=[c for c in report['cases'] if c['status']!='PASS']
    lines=['# 基线严格复现核验',f"\n状态：**{report['status']}**。缺失证据不会视为通过。",f"\n计数：{report['counts']}",
           '\n逐时数组绝对容差1e-6、相对容差1e-11；JSON数值绝对容差1e-5、相对容差1e-11。计费独立重算容差1e-4元，物理约束容差1e-5。',
           '\nNPZ按实际数组内容比较；压缩文件哈希只作证据绑定。运行时间不要求重现。', '\n## 未完成或不一致项\n']
    lines += [f"- {c['status']}：`{c['name']}`；{'; '.join(c.get('errors',[])) or c.get('reason','等待生成或见JSON细节')}" for c in bad]
    if not bad:lines.append('无。')
    args.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':report['status'],'counts':report['counts'],'report':str(args.output)},ensure_ascii=False))
    sys.exit({'PASS':0,'FAIL':1,'PENDING':2}[report['status']])

if __name__=='__main__':main()
