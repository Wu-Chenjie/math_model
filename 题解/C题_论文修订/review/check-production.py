"""Independent audit of 36 full production trajectories; no solver/model calls.

python3 review/check-production.py                     # partial live inventory
python3 review/check-production.py --require-complete  # final numerical gate

Energy, costs, physics, release reconstruction, and calendar rules below are
implemented independently with NumPy. No production module is imported.
Prior code/mutation/LP reviews are identified as reused evidence, not rerun here.
"""
from pathlib import Path
import hashlib, json, sys, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/production-audit.json'
ETA=.9; M=5000/6; EMIN=1200.; EMAX=10800.; INITIAL=6000.
DAYS=np.arange(31,365); DATES=np.arange(np.datetime64('2025-02-01'),np.datetime64('2026-01-01'))
TEND=365*144; TOL=1e-5
KINDS=['q2','q3','q4_2','q4_3']
METHODS=['closed_baseline','cross_baseline','affine_mpc','markov_mpc','closed_affine']
ABLATIONS={'0only':[0],'without6':[0,2,3],'without12':[0,1,3],'without18':[0,1,2]}
DATA=dict(np.load(ROOT/'artifacts/data.npz'))
MODEL_CACHE={}

class Pending(Exception):pass
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(test,message):
    if not bool(test):raise AssertionError(message)
def near(a,b,label,tol=TOL):
    aa=np.asarray(a);bb=np.asarray(b)
    err=float(np.max(np.abs(aa-bb))) if aa.size else 0.
    require(np.isfinite(err) and err<=tol,f'{label}: {err}')
    return err
def read_pair(stem):
    j=ROOT/(stem+'.json');n=ROOT/(stem+'.npz')
    if not j.exists() or not n.exists():raise Pending('Missing '+', '.join(str(p.relative_to(ROOT)) for p in [j,n] if not p.exists()))
    before={str(p.relative_to(ROOT)):sha(p) for p in [j,n]}
    try:
        meta=json.loads(j.read_text());arrays=dict(np.load(n))
    except (ValueError,EOFError,OSError) as e:raise Pending('Incomplete/unreadable pair: '+str(e))
    after={str(p.relative_to(ROOT)):sha(p) for p in [j,n]}
    if before!=after:raise Pending('Files changed during read')
    return arrays,meta,after

def daily_ledger(a):
    q,r,p,e=a['q'],a['r'],a['price'],a['emergency']
    ledger={'planned_cost':np.sum(p*q,axis=1),
            'increase_cost':np.sum(1.5*p*np.maximum(r-q,0),axis=1),
            'reduction_net_cost':np.sum(-.5*p*np.maximum(q-r,0),axis=1),
            'emergency_cost':np.sum(5*p*e,axis=1),
            'emergency_energy':e.sum(1),'spill_energy':a['spill'].sum(1),
            'projection_count':np.sum(a['projection']>1e-6,axis=1)}
    ledger['total_cost']=sum(ledger[k] for k in ['planned_cost','increase_cost','reduction_net_cost','emergency_cost'])
    near(ledger['total_cost'],np.sum(p*(np.maximum(1.5*r-.5*q,.5*r+.5*q)+5*e),axis=1),'two independent fee forms')
    return ledger

def physical(a,kind,initial,terminal=None,closed=False):
    nd=len(a['days']);days=np.asarray(a['days'])
    for key in ['q','r','c','d','emergency','spill','price','projection']:
        require(a[key].shape==(nd,144),key+' shape')
        require(np.isfinite(a[key]).all(),key+' finite')
    require(a['state'].shape==(nd,145),'state shape')
    require(np.isfinite(a['state']).all(),'state finite')
    near(a['dates'].astype('datetime64[D]').astype(int),DATA['dates'][days].astype('datetime64[D]').astype(int),'data date mapping',0)
    q,r,c,d,e,w,E=[a[k] for k in ['q','r','c','d','emergency','spill','state']]
    net=(DATA['load'][days]-DATA['pv'][days])/6
    prices=DATA['price'][days] if kind.startswith('q4') else np.broadcast_to(DATA['day_price'],(nd,144))
    near(a['price'],prices,'actual settlement price',0)
    nonnegative=float(max(0,-min(a[k].min() for k in ['q','r','c','d','emergency','spill','projection'])))
    require(nonnegative<=TOL,'negative physical energy')
    result={'balance_max_abs':near(r+e+d-c-w,net,'bus balance'),
            'soc_recurrence_max_abs':near(np.diff(E,axis=1),ETA*c-d/ETA,'SOC recurrence'),
            'midnight_jump_max_abs':near(E[1:,0],E[:-1,-1],'midnight continuity'),
            'soc_min':float(E.min()),'soc_max':float(E.max()),
            'power_max_kw':float(max(c.max(),d.max())*6),
            'simultaneous_max':near(np.minimum(c,d),0,'simultaneous charge/discharge'),
            'initial_inventory':float(E[0,0]),'final_inventory':float(E[-1,-1]),
            'negative_energy_violation':nonnegative}
    near(E[0,0],initial,'inherited initial inventory')
    require(result['soc_min']>=EMIN-TOL and result['soc_max']<=EMAX+TOL,'SOC limits')
    require(result['power_max_kw']<=5000+TOL,'power limit')
    if closed:near(E[:,-1],6000,'daily closure')
    if terminal is not None:near(E[-1,-1],terminal,'true terminal inventory')
    return result

def releases(a,kind):
    rel=a['releases'];nd=len(a['days']);require(rel.shape==(nd,4,144),'release shape')
    require(np.isfinite(rel[:,0]).all(),'midnight contracts missing')
    near(rel[:,0],a['q'],'original q locked to midnight snapshot')
    effective=rel[:,0].copy();adjust=kind in ['q3','q4_3']
    for k in range(1,4):
        require(np.isnan(rel[:,k,:k*36]).all(),'revision affects already delivered slots')
        if adjust:
            require(np.isfinite(rel[:,k,k*36:]).all(),'missing permitted revision')
            require(rel[:,k,k*36:].min()>=-TOL,'negative revised quantity')
            effective[:,k*36:]=rel[:,k,k*36:]
        else:require(np.isnan(rel[:,k]).all(),'Q2-type unauthorized revision')
    err=near(effective,a['r'],'latest legal release reconstructs final r')
    near(a['r'][:,:36],a['q'][:,:36],'first six hours locked')
    return {'passed':True,'final_r_reconstruction_error':err,'official_revision_nodes_per_day':4 if adjust else 1,
            'meaning':'r is delivery-wise final effective quantity; every original q equals its daily 00:00 snapshot.'}

def compare_reported_ledger(ledger,reported_daily,reported_totals,dates,E):
    require(len(reported_daily)==len(dates),'daily record length')
    maxerr=0.
    for i,row in enumerate(reported_daily):
        require(str(row['date'])==str(dates[i]),'daily report date')
        for key,value in ledger.items():maxerr=max(maxerr,near(row[key],value[i],f'daily {key}'))
        maxerr=max(maxerr,near(row['ending_inventory'],E[i,-1],'daily ending inventory'))
    if reported_totals is not None:
        for key,value in ledger.items():maxerr=max(maxerr,near(reported_totals[key],np.sum(value),f'annual {key}'))
    return maxerr

def model_metadata(kind,cutoff,days):
    suffix='' if days==3 else f'_D{days}'
    relative=f'artifacts/tails/{kind}_{cutoff}{suffix}.json'
    if relative not in MODEL_CACHE:
        path=ROOT/relative
        if not path.exists():raise Pending('Missing used tail '+relative)
        m=json.loads(path.read_text());cfg=m['configuration']
        require(cfg['cutoff_day_exclusive']==cutoff,'tail cutoff metadata')
        require(cfg['horizon_days']==days and cfg['steps_per_day']==12,'tail horizon/granularity')
        require(cfg['history_days']==list(range(max(0,cutoff-28),cutoff)),'tail mature complete-day window')
        require(cfg['variable_price']==kind.startswith('q4'),'tail price setting')
        require(cfg['adjustments']==(kind in ['q3','q4_3']),'tail adjustment setting')
        require(m['iterations']==500,'tail iterations differ from frozen development/evaluation budget')
        cuts=np.asarray(m['root_cuts']);require(cuts.ndim==2 and cuts.shape[1]==2 and np.isfinite(cuts).all(),'one-dimensional tail cuts')
        MODEL_CACHE[relative]={'sha256':sha(path),'configuration':cfg,'cut_count':len(cuts),'iterations':m['iterations']}
    return relative,MODEL_CACHE[relative]

def information(a,meta,kind,candidate,config,allowed=None):
    rows=meta['decisions'];require(len(rows)==len(a['days'])*4,'four planning nodes per day')
    closed=bool(config['closed_daily']);official=kind in ['q3','q4_3'];sddp=candidate.startswith('sddp')
    horizon=int(config['horizon_days']);count=int(config['count']);scale=float(config['tail_scale'])
    used=set();slack=[];tail_hist={};maxinv=0.;cover={}
    for i,day in enumerate(a['days']):
        for k in range(4):
            row=rows[i*4+k];now=int(day)*144+k*36;end=min((int(day)+horizon)*144,TEND);length=end-now
            require(row['as_of']==now and row['release']==k and row['end']==end,'planning absolute clock')
            require(row['date']==str(a['dates'][i]),'planning date')
            maxinv=max(maxinv,near(row['inventory'],a['state'][i,k*36],'planning input SOC'))
            # Derive all matured historical issues first, then use the most
            # recent 28; this is independent of the producer's search shortcut.
            historical=[h for h in range(7,int(day)) if h*144+k*36+length<=now][-28:]
            if count and len(historical)>count:
                positions=np.rint(np.linspace(0,len(historical)-1,count)).astype(int)
                historical=[historical[j] for j in positions]
            require(row['history_days']==historical,'mature residual block selection')
            last=max(historical)*144+k*36+length
            require(row['latest_training_target_exclusive']==last and last<=now,'last actual training target')
            slack.append(now-last)
            if official:
                nodes=range(4) if allowed is None else allowed
                issue=max(d*144+j*36 for d in [int(day)-1,int(day)] for j in nodes if d*144+j*36<=now)
                covered=max(0,min(end,issue+144)-now)
            else:covered=0
            require(row['official_covered_slots']==covered,'already released full-24h coverage')
            cover[str(covered)]=cover.get(str(covered),0)+1
            use_tail=sddp and not closed and end<TEND
            if use_tail:
                month=a['dates'][i].astype('datetime64[M]').astype('datetime64[D]')
                cutoff=int((month-np.datetime64('2025-01-01')).astype(int))
                D=min(3,(TEND-end)//144)
                require(D>=1 and row['tail_model_cutoff']==cutoff and row.get('tail_model_days')==D,'as-of month or remaining-day tail mismatch')
                path,model=model_metadata(kind,cutoff,D);used.add(path)
                require(1<=row['tail_cut_count']<=model['cut_count']+1,'active cut count')
                near(row['tail_price'],0,'SDDP replaces linear tail',0)
                tail_hist[str(D)]=tail_hist.get(str(D),0)+1
            else:
                require(row['tail_model_cutoff'] is None and row['tail_cut_count']==0 and row.get('tail_model_days') is None,'unexpected tail model')
                if closed or end==TEND:near(row['tail_price'],0,'true endpoint or constant closed tail',0)
                elif not kind.startswith('q4'):
                    near(row['tail_price'],scale*float(np.quantile(DATA['day_price'],.25))/ETA,'fixed-price linear tail',1e-10)
                else:require(np.isfinite(row['tail_price']) and row['tail_price']>=0,'variable-price linear tail finite')
    return {'passed':True,'decisions':len(rows),'minimum_training_maturity_slack_slots':int(min(slack)),
            'input_SOC_max_error':maxinv,'official_coverage_histogram':cover,
            'tail_days_histogram':tail_hist,'used_model_files':sorted(used),
            'scope_limit':'Checks recorded time/index permissions and file metadata. Nonanticipativity of the producing algorithm additionally relies on separately executed source/mutation reviews; it cannot be proved from one realized trajectory alone.'}

def ordinary_case(stem,kind,candidate,allowed=None):
    a,m,hs=read_pair(stem)
    near(a['days'],DAYS,'full annual day indices',0)
    near(a['dates'].astype('datetime64[D]').astype(int),DATES.astype(int),'full annual calendar',0)
    require(m['kind']==kind and m['candidate']==candidate,'method identity')
    cfg=m['configuration']
    require(cfg['start_day']==31 and cfg['end_day']==364 and cfg['final'] is None,'main evaluation endpoints')
    require(cfg['count']==7 and cfg['horizon_days']==2 and cfg['tail_scale']==1 and cfg['grid']==321,'matched production configuration')
    require(cfg['closed_daily']==candidate.startswith('closed_'),'daily closure configuration')
    require(cfg.get('initial',6000)==6000,'annual initial inventory configuration')
    if allowed is not None:
        design=m['validation_design']
        require(design['kind']=='q3' and design['start']==31 and design['stop']==365 and design['releases']==allowed,'release-ablation design')
        require(not design.get('stress',False),'annual ablation must not change actual data')
    phys=physical(a,kind,6000,closed=cfg['closed_daily']);rel=releases(a,kind);ledger=daily_ledger(a)
    fee_error=compare_reported_ledger(ledger,m['daily'],m['totals'],a['dates'],a['state'])
    for key,value in phys.items():near(m['validation'][key],value,'reported physical '+key)
    info=information(a,m,kind,candidate,cfg,allowed)
    return {'status':'pass','kind':kind,'candidate':candidate,'files':hs,'days':len(a['days']),
            'independent_totals':{k:float(v.sum()) for k,v in ledger.items()},
            'daily_and_annual_cost_reconciliation_max_abs':fee_error,'physical':phys,'releases':rel,'information':info}

def terminal_case(stem,kind,candidate):
    a,m,hs=read_pair(stem);source=f'artifacts/annual/{kind}_{candidate}'
    old,om,oh=read_pair(source)
    require(m['kind']==kind and m['candidate']==candidate,'terminal case identity')
    require(m['source_trajectory_sha256']==oh[source+'.npz'],'terminal source trajectory hash')
    for key in ['source_metrics_sha256','fixed_suffix_configuration','fixed_suffix_daily','fixed_suffix_decisions']:
        if key not in m:raise Pending('Missing terminal suffix audit evidence '+key)
    require(m['source_metrics_sha256']==oh[source+'.json'],'terminal source metrics hash')
    require(m['prefix_days']==332 and m['replayed_days']==[363,364],'terminal splice boundary')
    near(a['days'],DAYS,'terminal annual days',0)
    near(a['dates'].astype('datetime64[D]').astype(int),DATES.astype(int),'terminal annual calendar',0)
    require(set(a)==set(old),'spliced array columns')
    prefix_error=0.
    for key in a:
        if np.issubdtype(a[key].dtype,np.number):
            aa=a[key][:332];bb=old[key][:332]
            require(np.array_equal(np.isnan(aa),np.isnan(bb)),'prefix NaN masks '+key)
            prefix_error=max(prefix_error,near(np.nan_to_num(aa),np.nan_to_num(bb),'unchanged prefix '+key,0))
        else:require(np.array_equal(a[key][:332],old[key][:332]),'unchanged prefix '+key)
    phys=physical(a,kind,6000,terminal=6000);rel=releases(a,kind);ledger=daily_ledger(a)
    source_ledger=daily_ledger(old)
    near(m['free_total_cost'],source_ledger['total_cost'].sum(),'independent original free cost')
    near(m['fixed_total_cost'],ledger['total_cost'].sum(),'independent fixed cost')
    near(m['terminal_constraint_increment'],ledger['total_cost'].sum()-source_ledger['total_cost'].sum(),'terminal cost difference')
    require(max(m['free_suffix_replay_differences'].values())<=TOL,'producer reported free suffix replay failed')
    suffix={k:v[332:] for k,v in a.items()};cfg=m['fixed_suffix_configuration'];original=om['configuration']
    for key in ['count','horizon_days','tail_scale','grid']:require(cfg[key]==original[key],'fixed suffix configuration '+key)
    require(cfg['start_day']==363 and cfg['end_day']==364 and cfg['final']==6000 and not cfg['closed_daily'],'suffix endpoints')
    near(cfg['initial'],old['state'][332,0],'suffix initial configuration')
    near(m['suffix_initial_inventory'],old['state'][332,0],'reported inherited SOC')
    near(suffix['state'][0,0],old['state'][331,-1],'physical splice SOC')
    sp=physical(suffix,kind,float(old['state'][332,0]),terminal=6000)
    for key,value in sp.items():near(m['fixed_suffix_validation'][key],value,'suffix reported physical '+key)
    sl=daily_ledger(suffix)
    fee_error=compare_reported_ledger(sl,m['fixed_suffix_daily'],None,suffix['dates'],suffix['state'])
    info=information(suffix,{'decisions':m['fixed_suffix_decisions']},kind,candidate,cfg)
    prefix_info=information({k:v[:332] for k,v in old.items()},
                            {'decisions':om['decisions'][:332*4]},kind,candidate,original)
    near(ledger['total_cost'].sum(),source_ledger['total_cost'][:332].sum()+sl['total_cost'].sum(),'prefix plus fixed suffix fee')
    return {'status':'pass','kind':kind,'candidate':candidate,'files':hs,'source_files':oh,'days':334,
            'independent_totals':{k:float(v.sum()) for k,v in ledger.items()},'physical':phys,'releases':rel,
            'prefix_exact_max_error':prefix_error,'suffix_daily_cost_reconciliation_max_abs':fee_error,
            'information':{'prefix':prefix_info,'fixed_suffix':info},
            'replay_scope':'Independently verifies stored source hashes, every reused prefix element, splice SOC, suffix logs/fees and physical constraints. Does not rerun all eight controllers; prior v2 review independently replayed both Q2 linear-tail cases.'}

def main():
    begin=time.perf_counter();expected=[]
    for kind in KINDS:
        expected += [(f'artifacts/annual/{kind}_{c}',kind,c,None,False) for c in METHODS]
        expected += [(f'artifacts/annual_sddp/{kind}_sddp_markov',kind,'sddp_markov',None,False)]
    expected += [(f'artifacts/experiments/annual_pv_{n}','q3','markov_mpc',a,False) for n,a in ABLATIONS.items()]
    expected += [(f'artifacts/global-terminal/{k}_{c}',k,c,None,True) for k in KINDS for c in ['affine_mpc','markov_mpc']]
    require(len(expected)==36,'expected inventory count')
    cases={};pending=[];failed=[]
    for stem,kind,candidate,allowed,terminal in expected:
        try:
            result=terminal_case(stem,kind,candidate) if terminal else ordinary_case(stem,kind,candidate,allowed)
            cases[stem]=result;print('PASS '+stem,flush=True)
        except Pending as exc:
            cases[stem]={'status':'pending','reason':str(exc)};pending.append(stem)
        except Exception as exc:
            cases[stem]={'status':'fail','error_type':type(exc).__name__,'reason':str(exc)};failed.append(stem)
            print('FAIL '+stem+': '+str(exc),flush=True)
    reused={}
    for name in ['controller-checks.json','sddp-checks.json','v2-boundary-review.json','global-oracle.json']:
        p=ROOT/'review'/name
        if p.exists():reused[str(p.relative_to(ROOT))]=sha(p)
    status='fail' if failed else 'pending' if pending else 'all_36_pass_within_numerical_scope'
    code=1 if failed else 2 if pending and '--require-complete' in sys.argv else 0
    report={'schema_version':1,'reviewer_id':'/root/independent_review','independent':True,
            'scope':'Production numerical trajectories and recorded information permissions only; no ranking, score, or final project acceptance.',
            'status':status,'passed':not failed and not pending,'all_available_cases_passed':not failed,
            'expected_cases':36,'passed_cases':sum(v['status']=='pass' for v in cases.values()),
            'pending_cases':pending,'failed_cases':failed,'cases':cases,'used_tail_models':MODEL_CACHE,
            'formula_independence':'No production module imported. Bus balance, battery recurrence, fee piecewise identity, daily/annual aggregation, revision replay, calendar/maturity, tail-file calendar routing, and prefix splice checks are independent NumPy calculations in this file.',
            'reused_evidence':reused,
            'reuse_limitations':'Source nonanticipativity, future-data mutation, LP/SDDP dual validity, and deterministic fixed-suffix policy reproduction are covered by named earlier reviews. This script does not pretend that recorded timestamps alone prove those algorithmic properties and does not re-solve optimization models.',
            'audit_source_sha256':sha(__file__),'data_npz_sha256':sha(ROOT/'artifacts/data.npz'),
            'observed_production_source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src').glob('*.py')},
            'execution':{'command':'python3 review/check-production.py'+(' --require-complete' if '--require-complete' in sys.argv else ''),
                         'exit_code':code,'runtime_seconds':time.perf_counter()-begin,'python':sys.version,'numpy':np.__version__,
                         'deterministic_reason':'Exact calendar/index comparisons and deterministic array formulas; no sampling.'}}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    note=f'''# 生产轨迹独立审计

审查人 `/root/independent_review`。本次快照：应有36组，已通过{report['passed_cases']}组，待补{len(pending)}组，失败{len(failed)}组；状态 `{status}`。详细逐组结论、原文件哈希与缺项见production-audit.json。这里不作候选排名、模拟评分或最终项目验收。

运行 `python3 review/check-production.py` 更新现有产物快照。最终运行 `python3 review/check-production.py --require-complete`：缺项退出2，实质检查失败退出1，仅全部36组通过才退出0。

目标为20个普通年度、4个SDDP年度、4个全年预报消融、8个全局期末6000对照。每条年度轨迹覆盖334日、48,096个10分钟段、1336个重规划节点。

本脚本不导入任何生产模型模块。费用用两种等价分段表达式独立重算，并逐日及全年核对；能量平衡、SOC递推/边界、功率、互斥、午夜连续与真实末端直接由数组检验。原q必须等于0点发布快照，最终r由每段最新合法发布重建；已交付段不能调约，Q2不得有日内调约，头6小时r=q。

记录中的as-of、发布时点、当前库存、完整24小时预报覆盖、成熟连续历史块均重新按绝对时刻核算。SDDP检查当前月份、剩余D1/D2/D3、H=T零末值及实际被引用模型的训练截止/配置和哈希。全局期末对照另检查源NPZ与源JSON双哈希、全部332日前缀数组逐值一致、继承库存、固定后缀日志/费用和拼接。

复用的既有证据在JSON中逐项列出并哈希：算法非预见性与未来扰动、独立DP/LP比较、SDDP小树及对偶割、v2后缀实际复演。它们没有在本脚本中重跑；仅凭一条实测轨迹及其时间戳本身，无法证明生产程序没有读取不可见信息。本脚本也不从保存的NPZ声称重新验证了所有上层训练LP最优性。
'''
    (ROOT/'review/production-audit.md').write_text(note)
    print(json.dumps({'status':status,'passed':report['passed_cases'],'pending':len(pending),'failed':len(failed),
                      'seconds':report['execution']['runtime_seconds']}),flush=True)
    raise SystemExit(code)

if __name__=='__main__':main()
