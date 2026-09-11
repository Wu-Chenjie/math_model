"""Local orchestration of the remaining finite calculations, with no model calls."""
from pathlib import Path
import subprocess,sys,time,json,shutil
ROOT=Path(__file__).resolve().parents[1]

def complete(paths):
    for path in paths:
        try:
            m=json.loads(path.read_text())
            if m.get('iterations')!=500:return False
        except (OSError,ValueError):return False
    return True

def run(args):
    print('START', ' '.join(args),flush=True)
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)
    print('DONE', ' '.join(args),flush=True)

def main():
    kinds=['q2','q3','q4_2','q4_3'];cutoffs=[14,31,59,90,120,151,181,212,243,273,304,334]
    while not complete([ROOT/f'artifacts/tails/{k}_{d}_D1.json' for k in kinds for d in [14,334]]):time.sleep(10)
    run(['src/run.py','--phase','train','--cutoffs','14','334','--tail-days','2','--iterations','500','--workers','2'])
    run(['src/sddp.py','--cutoff','31','--days','1','--iterations','500','--output','tails/q2_31_D1.json'])
    print('WAIT monthly training models',flush=True)
    while not complete([ROOT/f'artifacts/tails/{k}_{d}.json' for k in kinds for d in cutoffs]):time.sleep(10)
    run(['src/run.py','--phase','calibrate_sddp_v2','--start','24','--stop','31','--candidates','sddp_mpc','sddp_markov','--workers','3'])
    select=ROOT/'artifacts/selection.json';old=json.loads(select.read_text());shutil.copy2(select,ROOT/'artifacts/selection-v1.json')
    for k in kinds:
        vals=old['development_costs'][k]
        for c in ['sddp_mpc','sddp_markov']:
            vals[c]=json.loads((ROOT/f'artifacts/calibrate_sddp_v2/{k}_{c}.json').read_text())['totals']['total_cost']
        chosen=min(vals,key=vals.get)
        if vals['markov_mpc']<=min(vals.values())*(1+old['relative_tie_tolerance']):chosen='markov_mpc'
        old['selected'][k]=chosen
        assert chosen!='sddp_mpc','Unexpected development selection: run its annual candidate before finishing.'
    old['sddp_training_iterations_development']=500
    old['v2_note']='Recomputed January SDDP comparisons after finite-end tail truncation and increased training. This selection code reads no annual cost.'
    select.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n');print('FROZEN SELECTION',old['selected'],flush=True)
    # The affinely executed SDDP variant lost clearly in January and is retained
    # as a development comparison. Annual SDDP comparison uses the selected
    # Markov feedback, changing only the continuation-value construction.
    a=subprocess.Popen([sys.executable,'src/run.py','--phase','annual_sddp','--start','31','--stop','365','--candidates','sddp_markov','--workers','3'],cwd=ROOT)
    b=subprocess.Popen([sys.executable,'src/validate.py','--scope','annual-releases','--workers','3'],cwd=ROOT)
    assert a.wait()==0;assert b.wait()==0
    print('WAIT main annual pool',flush=True)
    while True:
        try:
            m=json.loads((ROOT/'artifacts/execution-annual.json').read_text())
            if m['exit_code']==0 and len(m['results'])==20:break
        except (OSError,ValueError,KeyError):pass
        time.sleep(10)
    run(['src/check_terminal.py'])
    print('ALL NUMERICAL PHASES FINISHED; final assembly and independent audit still required',flush=True)

if __name__=='__main__':main()
