# -*- coding: utf-8 -*-
"""一键复跑全流程：预处理 → 四问求解 → 对照 → 结果文件 → 表格导出 → 图表 → 验证。
完整复跑约6-8分钟（含K敏感性重算）。
日常增量复跑（不重跑K敏感性）：python tables_export.py --skip-k
"""
import subprocess
import sys
import time

HERE = r'D:/shumo/shumoC/code'
STEPS = ['prep_data.py', 'p1_solve.py', 'p2_solve.py', 'p3_solve.py', 'p4_solve.py',
         'run_baseline_det.py', 'results_io.py', 'tables_export.py', 'figures.py',
         'validate.py']

for s in STEPS:
    t0 = time.time()
    print(f'>>> {s}', flush=True)
    r = subprocess.run([sys.executable, rf'{HERE}/{s}'])
    if r.returncode != 0:
        sys.exit(f'FAILED at {s} (exit {r.returncode})')
    print(f'<<< {s} done ({time.time() - t0:.0f}s)', flush=True)

print('ALL STEPS PASSED')
