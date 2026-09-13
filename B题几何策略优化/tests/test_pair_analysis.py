import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from pair_analysis import summarize
except ImportError:
    print('FAIL independent paired analysis is unavailable')
    raise SystemExit(1)

class PairedTests(unittest.TestCase):
    def test_known_savings(self):
        old=[dict(time_s=100.,avg_s=10.,runtime_s=.1),dict(time_s=200.,avg_s=20.,runtime_s=.2)]
        new=[dict(time_s=80.,avg_s=8.,runtime_s=.1),dict(time_s=160.,avg_s=16.,runtime_s=.2)]
        result=summarize(old,new)
        self.assertAlmostEqual(result['total_gain_pct'],20)
        self.assertAlmostEqual(result['saving_s_mean'],30)
        self.assertEqual(result['wins'],2)
    def test_equal(self):
        rows=[dict(time_s=100.,avg_s=10.,runtime_s=.1)]*3
        result=summarize(rows,rows)
        self.assertEqual(result['total_gain_pct'],0)
        self.assertEqual(result['ties'],3)
        self.assertEqual(result['saving_s_ci95'],[0,0])

if __name__=='__main__':unittest.main()
