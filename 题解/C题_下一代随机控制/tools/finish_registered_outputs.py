"""Finish this already-running registered experiment without dispatching it twice.

This is a single local task, not a scheduler. Numerical validation and the
frozen adoption gate remain in continue_registered_pipeline.py. Human/agent
visual inspection and three independent final reviews remain separate gates.
"""
from pathlib import Path
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime')
CORRUPT_STATE_TIMEOUT_SECONDS = 30.
sys.path.insert(0, str(ROOT/'tools'))
from certify_model_checks import certificate_is_current
from current_evidence import require_baseline_current, require_formal_current


def require_output_evidence():
    """Require the current certificate and the adoption report's exact evidence."""
    require_baseline_current(ROOT)
    require_formal_current(ROOT)
    paths = {'baseline_reproduction': 'artifacts/baseline-reproduction-check.json',
             'formal_physics': 'artifacts/formal-validation.json',
             'model_information_and_mathematics': 'artifacts/model-check-validation.json'}
    model = json.loads((ROOT/paths['model_information_and_mathematics']).read_text())
    assert certificate_is_current(model), 'Independent model certificate is stale or incomplete'
    adoption = json.loads((ROOT/'artifacts/model-adoption.json').read_text())
    assert adoption.get('status') == 'PASS' and adoption.get('pending') == [], 'Adoption has not passed'
    evidence = adoption.get('verification_gates', {})
    assert set(evidence) == set(paths), 'Adoption evidence coverage incomplete'
    for name, path in paths.items():
        assert evidence[name].get('status') == 'PASS', 'Adoption evidence has not passed: '+name
        assert evidence[name].get('sha256') == hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), 'Adoption evidence changed: '+name
    freeze_path = ROOT/'artifacts/frozen-development-selection.json'
    frozen = json.loads(freeze_path.read_text())
    assert adoption.get('selection_sha256') == hashlib.sha256(freeze_path.read_bytes()).hexdigest(), 'Adoption uses a stale January selection'
    assert adoption.get('challenger') == frozen['challenger'] and adoption.get('incumbent') == frozen['incumbent']
    economic = adoption.get('economic_gate_pass')
    assert isinstance(economic, bool), 'Adoption economic gate missing'
    expected = 'adopt_challenger' if economic else 'retain_incumbent'
    assert adoption.get('decision') == expected, 'Adoption decision disagrees with frozen gate'
    assert adoption.get('adopted_configuration') == frozen['challenger' if economic else 'incumbent'], 'Adoption selected an unregistered policy'
    questions = adoption.get('question_results', [])
    assert len(questions) == 4 and {q['kind'] for q in questions} == {'q2','q3','q4_2','q4_3'}, 'Adoption lacks all task settings'


def require_alive(pid):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise RuntimeError('Numerical pipeline has no valid process id')
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        raise RuntimeError('Numerical process ended without a completed result gate') from None


def ready(value):
    if value.get('status') == 'failed':
        raise RuntimeError('Registered numerical pipeline failed: ' + str(value.get('error')))
    return value.get('status') == 'complete' and value.get('stage') == 'computed_results_ready'


def main():
    records = []
    lock_fds = ()
    started = time.perf_counter()
    record_path = ROOT/'artifacts/output-continuation-execution.json'

    def state(stage, status='running', **extra):
        value = dict(status=status, stage=stage, pid=os.getpid(),
                     updated_utc=datetime.now(timezone.utc).isoformat(),
                     elapsed_seconds=time.perf_counter()-started, records=records, **extra)
        temporary = record_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        temporary.replace(record_path)

    def run(label, command):
        state(label)
        log = ROOT/f'artifacts/output-continuation-logs/{label}.log'
        log.parent.mkdir(exist_ok=True)
        before = time.perf_counter()
        with log.open('w') as output:
            result = subprocess.run([str(v) for v in command], cwd=ROOT,
                                    stdout=output, stderr=subprocess.STDOUT, pass_fds=lock_fds)
        records.append(dict(stage=label, command=[str(v) for v in command],
                            exit_code=result.returncode,
                            runtime_seconds=time.perf_counter()-before,
                            log=str(log.relative_to(ROOT))))
        if result.returncode:
            raise RuntimeError(f'{label} failed with exit {result.returncode}; inspect {log}')

    with (ROOT/'artifacts/output-continuation.lock').open('a') as own_lock:
        try:
            fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Output continuation already active')
        try:
            state('waiting_for_registered_numerical_pipeline')
            known_pid = None
            corrupt_since = None
            while True:
                # The older producer writes its state directly; retry a read
                # that happens between truncation and completion of that write.
                try:
                    value = json.loads((ROOT/'artifacts/pipeline-execution.json').read_text())
                except json.JSONDecodeError:
                    now = time.monotonic()
                    if corrupt_since is None:
                        corrupt_since = now
                    if known_pid is not None:
                        require_alive(known_pid)
                    if now-corrupt_since >= CORRUPT_STATE_TIMEOUT_SECONDS:
                        raise RuntimeError('Numerical state JSON remained incomplete past the retry deadline')
                    time.sleep(1)
                    continue
                corrupt_since = None
                known_pid = value.get('pid')
                if ready(value):
                    break
                require_alive(known_pid)
                time.sleep(10)
            # Serialize exports with the numerical producer and any one-key
            # reproduction. Re-read the completion gate after acquiring it.
            with (ROOT/'artifacts/pipeline.lock').open('a') as pipeline_lock:
                fcntl.flock(pipeline_lock, fcntl.LOCK_EX)
                pipeline_path = ROOT/'artifacts/pipeline-execution.json'
                if not ready(json.loads(pipeline_path.read_text())):
                    raise RuntimeError('Numerical completion changed before export lock')
                lock_fds = (own_lock.fileno(), pipeline_lock.fileno())
                require_output_evidence()
                numerical_sha = hashlib.sha256(pipeline_path.read_bytes()).hexdigest()
                run('information_terminal_independent', [sys.executable, 'review/check_information_terminal_independent.py'])
                run('selected_export', [sys.executable, 'tools/export_selected.py'])
                link = ROOT/'node_modules'
                if not link.exists():
                    link.symlink_to(RUNTIME/'dependencies/node/node_modules', target_is_directory=True)
                (ROOT/'artifacts/previews').mkdir(exist_ok=True)
                run('selected_workbooks', [RUNTIME/'dependencies/node/bin/node', 'tools/build_workbooks.mjs'])
                run('workbook_readback', [RUNTIME/'dependencies/python/bin/python3', 'tools/verify_workbooks.py'])
                run('paper_result_registry', [sys.executable, 'tools/build_paper_results.py'])
                run('paper_compile_and_render', [sys.executable, 'tools/build_paper.py'])
                state('rendered_outputs_ready', 'complete', numerical_pipeline_sha256=numerical_sha,
                      remaining=['Inspect all final PDF pages and workbook previews.',
                                 'Obtain three artifact-bound independent final reviews.',
                                 'Resolve findings and run finalization and project validation.'])
        except Exception as exc:
            state('stopped_on_error', 'failed', error=f'{type(exc).__name__}: {exc}')
            raise


if __name__ == '__main__':
    main()
