"""Falsification tests for the independent comparator, not the control model."""
import tempfile,unittest,json
from pathlib import Path
import numpy as np
from check_baseline_reproduction import Audit

class ComparatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.a=self.root/'a';self.b=self.root/'b';self.a.mkdir();self.b.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def audit(self):return Audit(self.a,self.b)
    def test_array_identity_not_compression(self):
        a={'q':np.array([6000.,30.]),'releases':np.array([np.nan,12.])}
        np.savez_compressed(self.a/'a.npz',**a);np.savez(self.b/'a.npz',**a)
        z=self.audit();z.compare_npz('a.npz');self.assertEqual(z.cases[-1]['status'],'PASS')
    def test_material_change_rejected(self):
        np.savez(self.a/'a.npz',q=[6000.,30.]);np.savez(self.b/'a.npz',q=[6000.,30.01])
        z=self.audit();z.compare_npz('a.npz');self.assertEqual(z.cases[-1]['status'],'FAIL')
    def test_nonfinite_trajectory_rejected(self):
        for p in (self.a,self.b):np.savez(p/'a.npz',q=[np.nan])
        z=self.audit();z.compare_npz('a.npz');self.assertEqual(z.cases[-1]['status'],'FAIL')
    def test_missing_is_pending(self):
        z=self.audit();z.compare_npz('missing.npz');self.assertEqual(z.cases[-1]['status'],'PENDING')
    def test_only_documented_metadata_default(self):
        a={'configuration':{'start_day':31},'decisions':[{'as_of':4464,'tail_model_cutoff':None,'tail_cut_count':0}]}
        b={'configuration':{'start_day':31,'initial':6000},'decisions':[{'as_of':4464,'tail_model_cutoff':None,'tail_cut_count':0,'tail_model_days':None}]}
        for p,o in ((self.a,a),(self.b,b)):(p/'a.json').write_text(json.dumps(o))
        z=self.audit();z.compare_json('a.json');self.assertEqual(z.cases[-1]['status'],'PASS')
        b['configuration']['initial']=6001;(self.b/'a.json').write_text(json.dumps(b))
        z=self.audit();z.compare_json('a.json');self.assertEqual(z.cases[-1]['status'],'FAIL')
    def test_contract_state_change_not_normalized(self):
        a={'decisions':[{'as_of':1,'tail_model_cutoff':1,'tail_cut_count':2}]}
        b={'decisions':[{'as_of':1,'tail_model_cutoff':1,'tail_cut_count':2,'tail_model_days':3}]}
        for p,o in ((self.a,a),(self.b,b)):(p/'a.json').write_text(json.dumps(o))
        z=self.audit();z.compare_json('a.json');self.assertEqual(z.cases[-1]['status'],'FAIL')

if __name__=='__main__':unittest.main()
