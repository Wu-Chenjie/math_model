"""Rebuild figures and full source listing; preserve reviewed manuscript tables.

Numerical inputs are frozen CSVs. This entry does not select models or rerun
experiments. Historical table generators must not overwrite reviewed labels.
"""
from pathlib import Path
import subprocess
import sys
R = Path(__file__).resolve().parents[1]
for script in ['build_overview_figure.py', 'build_readable_figures.py',
               'build_small_figures.py', 'build_source_appendix.py']:
    subprocess.run([sys.executable, str(R / 'src' / script)], cwd=R, check=True)
