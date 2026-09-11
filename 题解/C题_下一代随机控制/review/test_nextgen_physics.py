"""Independent auditor tests on existing complete replays plus controlled faults."""
from pathlib import Path
import copy,json,unittest
import numpy as np
from check_nextgen_physics import audit_arrays
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'baseline_frozen'

class PhysicalAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=dict(np.load(OLD/'artifacts/data.npz'));cls.fixtures={}
        for kind in ('q2','q3','q4_2','q4_3'):
            a=dict(np.load(OLD/f'artifacts/global-terminal/{kind}_markov_mpc.npz'))
            old=json.loads((OLD/f'artifacts/annual/{kind}_markov_mpc.json').read_text())
            fixed=json.loads((OLD/f'artifacts/global-terminal/{kind}_markov_mpc.json').read_text())
            m=copy.deepcopy(old);idx=fixed['prefix_days'];m['configuration'].update(initial=6000.,final=6000.)
            m['daily']=old['daily'][:idx]+fixed['fixed_suffix_daily']
            m['decisions']=old['decisions'][:idx*4]+fixed['fixed_suffix_decisions']
            m['totals']={k:float(sum(z[k] for z in m['daily'])) for k in old['totals']}
            cls.fixtures[kind]=(a,m)
    def test_existing_four_fixed_terminal_replays(self):
        for k,(a,m) in self.fixtures.items():
            r=audit_arrays(self.data,a,m)
            self.assertTrue(r['passed'],(k,r['errors']))
    def test_undeclared_free_terminal_fails(self):
        a,m=self.fixtures['q2'];m=copy.deepcopy(m);m['configuration']['final']=None
        r=audit_arrays(self.data,a,m);self.assertIn('hard_terminal_declared',r['errors'])
    def test_bill_drift_fails(self):
        a,m=self.fixtures['q3'];m=copy.deepcopy(m);m['totals']['total_cost']+=.1
        self.assertIn('aggregate:total_cost',audit_arrays(self.data,a,m)['errors'])
    def test_soc_reset_fails(self):
        a,m=self.fixtures['q2'];a={k:v.copy() for k,v in a.items()};a['state'][5,0]+=1
        r=audit_arrays(self.data,a,m);self.assertIn('midnight_jump_max_abs',r['errors'])
    def test_wrong_effective_contract_fails(self):
        a,m=self.fixtures['q3'];a={k:v.copy() for k,v in a.items()};a['r'][5,40]+=1
        self.assertIn('effective_r_reconstructed',audit_arrays(self.data,a,m)['errors'])
    def test_delivered_release_rewrite_fails(self):
        a,m=self.fixtures['q3'];a={k:v.copy() for k,v in a.items()};a['releases'][5,1,0]=0
        self.assertIn('release1_past_delivery_unset',audit_arrays(self.data,a,m)['errors'])
    def test_immature_block_fails(self):
        a,m=self.fixtures['q2'];m=copy.deepcopy(m);m['decisions'][0]['history_days']=[31]
        self.assertIn('mature_whole_blocks:4464',audit_arrays(self.data,a,m)['errors'])
    def test_declared_legacy_horizon_passes_and_wrong_end_fails(self):
        a,m=self.fixtures['q2'];m=copy.deepcopy(m)
        m['configuration'].update(horizon_hours=48,horizon_mode='legacy')
        result=audit_arrays(self.data,a,m)
        self.assertTrue(result['passed'],result['errors'])
        m['decisions'][1]['end']+=36
        result=audit_arrays(self.data,a,m)
        self.assertIn('legacy_horizon:4500',result['errors'])
    def test_horizon_extension_fails(self):
        a,m=self.fixtures['q2'];m=copy.deepcopy(m);m['configuration']['horizon_hours']=48
        r=audit_arrays(self.data,a,m);self.assertTrue(any(k.startswith('fixed_horizon:') for k in r['errors']))

if __name__=='__main__':unittest.main()
