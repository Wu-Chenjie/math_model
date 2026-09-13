"""Exact arithmetic for the illustrative oracle example; not a policy experiment."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib, json, time
R = Path(__file__).resolve().parents[1]
start = time.perf_counter()
n0, n1, r, v, d = 10, 11, 20, 5, 1800
t0 = Q(5 * n0)
t1 = Q(5 * n1) + Q(d - r, v)
mu0, mu1 = t0 / n0, t1 / n1
assert mu1 > mu0
assert mu1 - mu0 == (n0 * (t1 - t0) - t0) / (n0 * n1)
# The first ten distinct centers may be (0,0),...,(9,0), all within the start disk.
# All points are collinear and nonnegative, so the farthest left disk endpoint
# proves the exact open path optimum after adding (1800,0).
assert max(0, max(range(10)) - r) == 0
assert max(0, d - r) == 1780


def statement_sha():
    """Hash the problem statement if a copy is shipped; otherwise record the absence."""
    for cand in (R.parents[1] / 'inputs' / 'B题.pdf',
                 R.parents[2] / 'inputs' / 'B题.pdf'):
        if cand.is_file():
            return hashlib.sha256(cand.read_bytes()).hexdigest()
    return 'not shipped in this package (see the official problem statement)'


out = {
    'status': 'PASS', 'kind': 'exact illustrative calculation, not simulation',
    'constants': {'speed_m_s': v, 'clear_radius_m': r, 'successful_clear_s': 5,
                  'switch_s': 1, 'bearing_s': 5, 'failed_optical_s': 3,
                  'sources_min': 10, 'sources_max': 16},
    'example': {'source_counts': [n0, n1], 'distance_m': d, 'added_route_m': d - r,
                'total_time_s': [float(t0), float(t1)],
                'mean_time_s': [float(mu0), float(mu1)],
                'mean_time_exact': [str(mu0), str(mu1)],
                'marginal_identity_exact': True},
    'input_statement_sha256': statement_sha(),
    'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'runtime_s': time.perf_counter() - start,
    'limitations': ['No new cross-policy empirical validation.',
                    'No independent mathematical review.']}
(R / 'artifacts/algebra-check.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
