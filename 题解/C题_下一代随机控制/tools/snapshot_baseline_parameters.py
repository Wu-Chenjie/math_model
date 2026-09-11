"""Record accepted parameters by importing unchanged baseline definitions only."""
from pathlib import Path
import hashlib
import inspect
import json
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT.parent / 'C题_下一代基线复现'
sys.path.insert(0, str(REPLAY / 'src'))
import control
import forecasting
import run
import sddp
import numpy as np


def defaults(function):
    return {name: item.default for name, item in inspect.signature(function).parameters.items()
            if item.default is not inspect.Parameter.empty}


def main():
    data = np.load(REPLAY / 'artifacts/data.npz')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((REPLAY / 'src').glob('*.py'))}
    version = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    result = {
        'status': 'frozen_definitions_only_reproduction_gate_pending',
        'code_version_kind': 'SHA256 source manifest (no git revision assumed)',
        'code_version': version,
        'source_sha256': hashes,
        'physical': {name: getattr(control, name) for name in ['ETA', 'M', 'EMIN', 'EMAX', 'INITIAL']},
        'scenario_defaults': defaults(forecasting.scenarios),
        'simulation_defaults': defaults(run.simulate),
        'sddp_training_defaults': defaults(sddp.train_tail),
        'executed_sddp_iterations': 500,
        'candidate_definitions': run.CANDIDATES,
        'candidate_definition_columns': ['affine', 'lower_controller', 'tail', 'daily_closed'],
        'question_permissions': run.KINDS,
        'permission_columns': ['official_pv_forecasts_and_revision', 'variable_price'],
        'forecast_selection': json.loads((REPLAY / 'artifacts/forecast-selection.json').read_text()),
        'evaluation': {'start': str(data['dates'][31]), 'end': str(data['dates'][364]),
                       'days': len(data['dates'][31:365]), 'initial_kwh': control.INITIAL,
                       'legacy_main_final': None, 'matched_terminal_final_kwh': control.INITIAL},
        'legacy_horizon_hours_by_release': {str(t // 6): (288 - t) / 6 for t in range(0, 144, 36)},
        'environment': {'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform()},
        'scope': 'Definitions read from the unchanged replay; no simulation, tuning or upgraded model executed.'
    }
    target = ROOT / 'artifacts/baseline-parameters.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'code_version': version, 'evaluation': result['evaluation']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
