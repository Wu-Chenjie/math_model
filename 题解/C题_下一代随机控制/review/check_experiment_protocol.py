#!/usr/bin/env python3
"""Independent orchestration/meter/bootstrap checks; all fake runs in temp dirs.

No optimizer, development or annual policy replay is executed. Producer functions
are imported, redirected to isolated temporary roots and supplied fixture bills.
"""
from pathlib import Path
from dataclasses import asdict
import tempfile,hashlib,json,sys,traceback,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
import run_incremental_experiments as experiment
import compare_incremental_results as comparison
from nextgen_scenarios import Config


def run():
    tests=[];issues=[]
    def setup_fixture(root):
        (root/'artifacts').mkdir(exist_ok=True)
        (root/'tools').mkdir(exist_ok=True)
        shutil.copy2(ROOT/'tools/run_incremental_experiments.py',root/'tools/run_incremental_experiments.py')
        experiment.__file__=str(root/'tools/run_incremental_experiments.py')
        for name in ('data.npz','forecast-selection.json','development-forecast-selection.json'):
            (root/'artifacts'/name).write_text('{}')
    def test(name,fn):
        try:tests.append({'name':name,'status':'PASS','details':fn()})
        except Exception as exc:tests.append({'name':name,'status':'FAIL','error':str(exc),'traceback':traceback.format_exc()})
    def bootstrap():
        indices=comparison.block_indices();again=comparison.block_indices()
        assert indices.shape==(10000,334) and np.array_equal(indices,again)
        assert indices.min()>=0 and indices.max()<334
        for start in range(0,334,7):assert np.all(np.diff(indices[:,start:min(start+7,334)],axis=1)==1)
        dates=np.arange(np.datetime64('2025-02-01'),np.datetime64('2026-01-01')).astype(str).tolist()
        b={'dates':dates,'total_cost':np.full(334,100.),'emergency_cost':np.zeros(334),'emergency_kwh':np.zeros(334),'spill_kwh':np.zeros(334),'ending_inventory_kwh':np.full(334,6000.),'min_soc':.1,'max_soc':.9,'initial':6000.,'final':6000.}
        c={**b,'total_cost':np.full(334,98.)};result,rows,saving=comparison.pair(c,b,indices)
        assert result['saving_yuan']==668 and result['bootstrap_95_lower_yuan']==668 and result['bootstrap_95_upper_yuan']==668
        serial=5*np.sin(np.arange(334)/17)+np.arange(334)/334
        c={**b,'total_cost':100-serial};result,_,saving=comparison.pair(c,b,indices)
        loop=np.array([sum(float(saving[i]) for i in row) for row in indices])
        expected=np.quantile(loop,[.025,.975]);actual=[result['bootstrap_95_lower_yuan'],result['bootstrap_95_upper_yuan']]
        assert np.allclose(expected,actual,rtol=0,atol=1e-9)
        rejected=False
        try:comparison.pair({**c,'final':1200.},b,indices)
        except AssertionError:rejected=True
        assert rejected
        return {'index_shape':list(indices.shape),'block_internal_continuity':True,'constant_annual_saving_and_CI':668,'serial_fixture_quantile_max_error':float(np.max(np.abs(expected-actual))),'mismatched_terminal_rejected':True}
    test('paired_non_circular_moving_block_bootstrap',bootstrap)
    def bill():
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'fixture.npz';q=np.array([[100.,100.,100.]]);r=np.array([[80.,100.,130.]]);e=np.array([[2.,3.,4.]]);price=np.array([[.2,.5,1.3]])
            np.savez(p,q=q,r=r,emergency=e,price=price,dates=np.array(['2025-02-01']),spill=np.zeros_like(q),state=np.array([[6000.,6100.,6200.,6000.]]))
            actual=comparison.daily_ledger(p)['total_cost'][0]
            expected=.2*(100-.5*20+5*2)+.5*(100+5*3)+1.3*(100+1.5*30+5*4)
            assert abs(actual-expected)<1e-12
            return {'independently_computed_bill':expected,'code_bill':float(actual)}
    test('four_component_delivery_bill',bill)
    def january_only():
        original=experiment.ROOT
        try:
            with tempfile.TemporaryDirectory() as td:
                experiment.ROOT=Path(td);a=Config();b=Config(horizon_hours=72)
                for phase in ('development','formal'):
                    (Path(td)/'artifacts'/phase).mkdir(parents=True)
                    for c,cost in ((a,100.),(b,99.)):
                        for kind in experiment.KINDS:
                            p=Path(td)/f'artifacts/{phase}/{kind}_{c.identity()}.json'
                            p.write_text(json.dumps({'totals':{'total_cost':cost}}))
                chosen,evidence=experiment.choose([a,b]);assert chosen==b
                for p in (Path(td)/'artifacts/formal').glob('*.json'):p.write_text('{"totals":{"total_cost":1e99}}')
                other,other_evidence=experiment.choose([a,b]);assert other==chosen and evidence==other_evidence
                return {'formal_bill_mutation_has_no_effect':True,'chosen_H':chosen.horizon_hours}
        finally:experiment.ROOT=original
    test('selection_ignores_formal_bills',january_only)
    def protocol_guard():
        original_root,original_execute,original_file=experiment.ROOT,experiment.execute_group,experiment.__file__
        called=[]
        try:
            with tempfile.TemporaryDirectory() as td:
                experiment.ROOT=Path(td);setup_fixture(Path(td))
                experiment.preregister()
                frozen={'status':'frozen','source_hashes':{},'protocol_sha256':'deliberately-wrong','annual_configurations':[asdict(Config())]}
                (Path(td)/'artifacts/frozen-development-selection.json').write_text(json.dumps(frozen))
                experiment.execute_group=lambda *args:called.append(args) or []
                rejected=False
                try:experiment.annual(1)
                except (AssertionError,ValueError,RuntimeError,KeyError):rejected=True
                if not rejected and called:issues.append({'id':'PROTO-01','severity':'adoption_blocker','detail':'annual accepts a frozen selection whose protocol_sha256 deliberately disagrees with registration.'})
                assert rejected and not called,'bad protocol must be rejected before dispatch'
                frozen['protocol_sha256']=hashlib.sha256((Path(td)/'artifacts/experiment-protocol.json').read_bytes()).hexdigest()
                frozen['integrity_hashes']={'tampered':'digest'}
                (Path(td)/'artifacts/frozen-development-selection.json').write_text(json.dumps(frozen))
                integrity_rejected=False
                try:experiment.annual(1)
                except (AssertionError,ValueError,RuntimeError,KeyError):integrity_rejected=True
                assert integrity_rejected and not called,'bad integrity must be rejected before dispatch'
                return {'bad_protocol_hash_rejected_before_dispatch':rejected,'bad_integrity_rejected_before_dispatch':integrity_rejected,'fake_annual_dispatch_called':bool(called)}
        finally:experiment.ROOT,experiment.execute_group,experiment.__file__=original_root,original_execute,original_file
    test('annual_protocol_digest_guard',protocol_guard)
    def workflow():
        originals=(experiment.ROOT,experiment.execute_group,experiment.select_forecast,experiment.__file__)
        try:
            with tempfile.TemporaryDirectory() as td:
                experiment.ROOT=Path(td);setup_fixture(Path(td))
                def fake_execute(configs,phase,workers):
                    assert phase=='development'
                    for c in configs:
                        for kind in experiment.KINDS:
                            # Grid change alters feedback and can cause new bound hits.
                            hit=10 if c.grid==161 and c.gain_bound<20 else 0
                            m={'totals':{'total_cost':700.},'daily':[{'total_cost':100.} for _ in range(7)],'decisions':[{'gain_active_count':10,'gain_bound_hit_count':hit}]}
                            p=Path(td)/f'artifacts/development/{kind}_{c.identity()}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(m))
                    return []
                experiment.execute_group=fake_execute;experiment.select_forecast=lambda:{'fusion_weight':1.,'official_correction':0.}
                experiment.development(1)
                p=Path(td)/'artifacts/frozen-development-selection.json';frozen=json.loads(p.read_text());first=p.read_bytes()
                assert all(c['final']==6000 for c in frozen['annual_configurations'])
                assert {Config(**c).identity() for stage in frozen['stages'] for c in stage['configurations']} <= {Config(**c).identity() for c in frozen['annual_configurations']}
                if frozen['gain_hit_ratio_at_freeze']>.05 and frozen['challenger']['gain_bound']<80:
                    issues.append({'id':'PROTO-02','severity':'adoption_blocker','detail':'Fixture grid refinement changes gain hits after expansion stage; final freeze has100percent hits at bound5 without re-expansion.'})
                (Path(td)/'artifacts/formal').mkdir();(Path(td)/'artifacts/formal/already_started.json').write_text('{}')
                rejected=False
                try:experiment.development(1)
                except (AssertionError,ValueError,RuntimeError):rejected=True
                if not rejected and p.read_bytes()!=first:
                    issues.append({'id':'PROTO-03','severity':'adoption_blocker','detail':'development can overwrite frozen selection after formal results directory contains a run marker.'})
                assert rejected and p.read_bytes()==first,'frozen selection must remain immutable'
                assert frozen['gain_hit_ratio_at_freeze']<=.05 or frozen['challenger']['gain_bound']==80
                guard_checks=[]
                p.unlink()
                for marker in ('formal-directory','formal-start.json','execution-formal.json'):
                    if marker!='formal-directory':
                        for file in (Path(td)/'artifacts/formal').glob('*'):file.unlink()
                        (Path(td)/'artifacts'/marker).write_text('{}')
                    refused=False
                    try:experiment.require_unfrozen_development()
                    except RuntimeError:refused=True
                    assert refused,marker
                    guard_checks.append(marker)
                    if marker!='formal-directory':(Path(td)/'artifacts'/marker).unlink()
                return {'guards_independently_rejected':guard_checks,'registered_configurations':len(frozen['annual_configurations']),'all_stage_configurations_registered':True,
                        'final_gain_hit_ratio':frozen['gain_hit_ratio_at_freeze'],'final_gain_bound':frozen['challenger']['gain_bound'],
                        'redevelopment_after_formal_start_rejected':rejected}
        finally:experiment.ROOT,experiment.execute_group,experiment.select_forecast,experiment.__file__=originals
    test('staged_dependencies_final_gain_and_immutable_freeze',workflow)
    def final_matched_downgrade():
        originals=(experiment.ROOT,experiment.execute_group,experiment.select_forecast,experiment.__file__)
        try:
            with tempfile.TemporaryDirectory() as td:
                experiment.ROOT=Path(td);setup_fixture(Path(td))
                def fake_execute(configs,phase,workers):
                    assert phase=='development'
                    for c in configs:
                        # M1 wins at tail1, chooses tail0, but matched M0 wins at tail0.
                        cost=(680. if c.lower=='M1' else 670.) if c.tail_scale==0 else (693. if c.lower=='M1' else 700.)
                        for kind in experiment.KINDS:
                            value={'totals':{'total_cost':cost},'daily':[{'total_cost':cost/7} for _ in range(7)],'decisions':[{'gain_active_count':10,'gain_bound_hit_count':0}]}
                            path=Path(td)/f'artifacts/development/{kind}_{c.identity()}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
                    return []
                experiment.execute_group=fake_execute;experiment.select_forecast=lambda:{'fusion_weight':1.,'official_correction':0.}
                experiment.development(1)
                frozen=json.loads((Path(td)/'artifacts/frozen-development-selection.json').read_text())
                assert frozen['M1_development_pass'] is True
                assert frozen['final_M1_development_pass'] is False
                assert frozen['challenger']['lower']=='M0' and frozen['challenger']['tail_scale']==0
                m0=frozen['final_matched_M0'];m1=frozen['final_matched_M1']
                assert {k:v for k,v in m0.items() if k!='lower'}=={k:v for k,v in m1.items() if k!='lower'}
                ids={Config(**c).identity() for c in frozen['annual_configurations']}
                assert Config(**m0).identity() in ids and Config(**m1).identity() in ids
                return {'initial_M1_pass':True,'final_matched_M1_pass':False,'frozen_lower':'M0','final_tail_scale':0,'matched_pair_registered':True}
        finally:experiment.ROOT,experiment.execute_group,experiment.select_forecast,experiment.__file__=originals
    test('M1_tail_change_requires_matched_recheck_and_downgrade',final_matched_downgrade)
    def representative_selection_restriction():
        originals=(experiment.ROOT,experiment.execute_group,experiment.select_forecast,experiment.__file__)
        try:
            with tempfile.TemporaryDirectory() as td:
                experiment.ROOT=Path(td);setup_fixture(Path(td))
                def fake_execute(configs,phase,workers):
                    assert phase=='development'
                    for c in configs:
                        # Forbidden main counts dominate numerically but must remain diagnostics.
                        cost=1. if c.scenarios==5 else 2. if c.scenarios==14 else 645. if c.scenarios==10 else 650. if c.scenario_method=='conditional' else 700.
                        for kind in experiment.KINDS:
                            value={'totals':{'total_cost':cost},'daily':[{'total_cost':cost/7} for _ in range(7)],'decisions':[{'gain_active_count':10,'gain_bound_hit_count':0}]}
                            path=Path(td)/f'artifacts/development/{kind}_{c.identity()}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
                    return []
                experiment.execute_group=fake_execute;experiment.select_forecast=lambda:{'fusion_weight':1.,'official_correction':0.}
                experiment.development(1)
                frozen=json.loads((Path(td)/'artifacts/frozen-development-selection.json').read_text())
                sensitivity=next(s for s in frozen['stages'] if s['name']=='representative_count_sensitivity')
                selecting=next(s for s in frozen['stages'] if s['name']=='representative_count_main_selection')
                assert sensitivity['selecting'] is False and selecting['selecting'] is True
                assert {c['scenarios'] for c in selecting['configurations']}=={7,10}
                assert frozen['challenger']['scenarios']==10
                registered={c['scenarios'] for c in frozen['annual_configurations']}
                assert {5,7,10,14}<=registered
                return {'S5_cost':1.,'S14_cost':2.,'allowed_S10_cost':645.,'selected_scenarios':10,'all_sensitivity_counts_annual_registered':True}
        finally:experiment.ROOT,experiment.execute_group,experiment.select_forecast,experiment.__file__=originals
    test('S5_S14_cannot_enter_main_even_if_cheapest',representative_selection_restriction)


    paths=[ROOT/'tools/run_incremental_experiments.py',ROOT/'tools/compare_incremental_results.py']
    report={'reviewer_id':'/root/upgrade_code_review','independent':True,'status':'CHANGES_REQUESTED' if issues or any(t['status']=='FAIL' for t in tests) else 'PASS_WITHIN_SCOPE',
            'scope':'Temporary fixtures only; no actual optimization or model selection was run or changed. Guard failures are demonstrated vulnerabilities, not allegations of observed formal-period retuning.',
            'tests':tests,'issues':issues,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (ROOT/'review/protocol-comparison-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'issues':issues,'tests':[(t['name'],t['status']) for t in tests]},ensure_ascii=False))
    return 1 if issues or any(t['status']=='FAIL' for t in tests) else 0
if __name__=='__main__':sys.exit(run())
