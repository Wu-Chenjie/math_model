#!/usr/bin/env python3
"""M1 adoption masking fixtures; no numerical policy or valid certificate forged.

Main is redirected to an isolated directory and supplied synthetic daily ledgers.
Verification reports are intentionally absent: every fixture must stay PENDING,
while its economic/M1 decision logic is independently checked.
"""
from pathlib import Path
from dataclasses import asdict,replace
import tempfile,json,sys,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
import evaluate_adoption as adoption
from nextgen_scenarios import Config


def run():
    cases=[];originals=adoption.ROOT,adoption.daily_ledger
    dates=np.arange(np.datetime64('2025-02-01'),np.datetime64('2026-01-01')).astype(str).tolist()
    def ledger(cost):
        return {'dates':dates,'total_cost':np.full(334,cost),'emergency_cost':np.zeros(334),'emergency_kwh':np.zeros(334),'spill_kwh':np.zeros(334),'ending_inventory_kwh':np.full(334,6000.),'min_soc':.1,'max_soc':.9,'initial':6000.,'final':6000.}
    try:
        for name,m0cost,expected in [('other_modules_mask_M1_loss',89.,False),('direct_M1_gain',95.,True),('M1_zero_contribution',90.,False)]:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);adoption.ROOT=root;(root/'artifacts/formal').mkdir(parents=True)
                challenger=Config(lower='M1',scenario_method='conditional',tail_scale=.5)
                matched=replace(challenger,lower='M0');incumbent=Config(horizon_mode='legacy')
                frozen={'status':'frozen','challenger':asdict(challenger),'incumbent':asdict(incumbent),'final_matched_M0':asdict(matched),
                        'final_matched_M1':asdict(challenger),'final_M1_development_pass':True,'annual_configurations':[asdict(incumbent),asdict(matched),asdict(challenger)]}
                (root/'artifacts/frozen-development-selection.json').write_text(json.dumps(frozen))
                for kind in ('q2','q3','q4_2','q4_3'):(root/f'artifacts/formal/{kind}_{challenger.identity()}.npz').touch()
                def read_fixture(path):
                    path=str(path)
                    if 'baseline_frozen' in path:return ledger(100.)
                    if matched.identity() in path:return ledger(m0cost)
                    if challenger.identity() in path:return ledger(90.)
                    raise AssertionError('unexpected candidate')
                adoption.daily_ledger=read_fixture
                try:adoption.main()
                except SystemExit as exc:assert exc.code==2
                report=json.loads((root/'artifacts/model-adoption.json').read_text())
                assert report['checks']['normalized_mean_saving_at_least_0_1_percent']
                direct=report['M1_direct_matched_M0_gate']
                assert direct['economic_gate_pass']==expected,(name,direct)
                assert report['economic_gate_pass']==expected
                assert report['status']=='PENDING' and report['decision']=='await_verification' and report['adopted_configuration'] is None
                # A status-only/empty physical certificate must not satisfy coverage.
                (root/'artifacts/formal-validation.json').write_text(json.dumps({'status':'PASS','frozen_selection_sha256':hashlib.sha256((root/'artifacts/frozen-development-selection.json').read_bytes()).hexdigest(),'records':[]}))
                try:adoption.main()
                except SystemExit as exc:assert exc.code==2
                incomplete=json.loads((root/'artifacts/model-adoption.json').read_text())
                assert incomplete['verification_gates']['formal_physics']['status']!='PASS'
                cases.append({'name':name,'overall_saving_percent':report['mean_question_saving_percent'],
                    'M1_direct_saving_percent':direct['mean_question_saving_percent'],'M1_direct_gate':direct['economic_gate_pass'],
                    'combined_economic_gate':report['economic_gate_pass'],'missing_certificates_prevent_adoption':True,'empty_physics_certificate_rejected':True})
    finally:adoption.ROOT,adoption.daily_ledger=originals
    path=ROOT/'tools/evaluate_adoption.py'
    report={'reviewer_id':'/root/upgrade_code_review','independent':True,'status':'PASS_WITHIN_SCOPE','scope':'Synthetic ledgers in temporary directories. No valid physics, source or independence certificate supplied; overall status must stayPENDING. Tests economic masking only.','cases':cases,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (ROOT/'review/adoption-matched-M1-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':run()
