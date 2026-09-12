"""Export specified-day Q2 positive emergency runs from the new fixed-end trajectory."""
from pathlib import Path
import hashlib
import json
import numpy as np

OUT = Path(__file__).resolve().parents[1]
SOURCE = OUT.parent / 'C题_下一代随机控制/artifacts/formal/q2_6cfbc0fe34fd0999.npz'
DATES = ['2025-03-20', '2025-06-21', '2025-09-23', '2025-12-21']
TOLERANCE = 1e-6

def clock(boundary):
    minutes = int(boundary) * 10
    return f'{minutes // 60:02d}:{minutes % 60:02d}'

def main():
    a = dict(np.load(SOURCE))
    result = {'source': str(SOURCE.relative_to(OUT.parent)),
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'candidate': '6cfbc0fe34fd0999', 'units': 'kWh',
              'positive_tolerance_kwh': TOLERANCE,
              'interval_convention': 'Merge consecutive ten-minute slots strictly above tolerance; half-open start/end intervals.',
              'dates': {}}
    for date in DATES:
        day = list(a['dates'].astype(str)).index(date)
        energy = a['emergency'][day]
        assert energy.shape == (144,) and energy.min() >= -1e-10
        positive = np.flatnonzero(energy > TOLERANCE)
        groups = np.split(positive, np.flatnonzero(np.diff(positive) > 1) + 1) if len(positive) else []
        intervals = [{'start_slot': int(g[0]), 'end_slot_exclusive': int(g[-1] + 1),
                      'interval': f'{clock(g[0])}--{clock(g[-1] + 1)}',
                      'energy_kwh': float(energy[g].sum())} for g in groups]
        total = float(energy.sum())
        merged = float(sum(row['energy_kwh'] for row in intervals))
        residual = total - merged
        # Compare to the original daily total, separately exposing subthreshold solver residue.
        assert abs(merged - float(energy[positive].sum())) < 1e-10
        assert abs(residual) < 1e-6, (date, residual)
        result['dates'][date] = {'intervals': intervals, 'daily_total_kwh': total,
                                'merged_interval_total_kwh': merged,
                                'subthreshold_residual_kwh': residual,
                                'daily_reconciliation_passed': True}
    lines = [r'\begin{table}[htbp]\centering\small',
             r'\caption{问题二四个指定日期的连续紧急购电区间（kWh）}\label{tab:q2-emergency}',
             r'\setlength{\tabcolsep}{3pt}',
             r'\begin{tabular}{lrlrlrlr}\toprule',
             ' & '.join(r'\multicolumn{2}{c}{' + date + '}' for date in DATES) + r' \\',
             ' & '.join(['时间段 & 电量'] * 4) + r' \\\midrule']
    count = max(len(result['dates'][d]['intervals']) for d in DATES)
    for row in range(count):
        cells = []
        for date in DATES:
            intervals = result['dates'][date]['intervals']
            cells += ([intervals[row]['interval'], f"{intervals[row]['energy_kwh']:.2f}"] if row < len(intervals)
                      else (['无', '0.00'] if row == 0 and not intervals else ['--', '--']))
        lines.append(' & '.join(cells) + r' \\')
    lines.append(r'\midrule')
    lines.append(' & '.join('全天合计 & ' + f"{result['dates'][d]['daily_total_kwh']:.2f}" for d in DATES) + r' \\')
    lines += [r'\bottomrule\end{tabular}',
              r'\par\vspace{1mm}\begin{minipage}{.97\linewidth}\footnotesize',
              r'逐段紧急购电量大于$10^{-6}$ kWh时计入区间；仅合并连续十分钟段。区间量与原轨迹全天总量之差均小于$10^{-6}$ kWh，差额为低于阈值的数值残差。',
              r'\end{minipage}\end{table}']
    (OUT / 'tables/q2-emergency.tex').write_text('\n'.join(lines) + '\n')
    (OUT / 'artifacts/q2-emergency.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
