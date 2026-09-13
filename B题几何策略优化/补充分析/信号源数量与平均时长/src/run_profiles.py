import concurrent.futures,hashlib,json,platform,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];P=R.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze={'created_unix':time.time(),'method':78,'training_csv':'../../results/iid78.csv','training_sha256':sha(P/'results/iid78.csv'),'training_seeds':[2610001,2610200],'new_validation_seeds':[2710001,2710200],'cases_per_question_per_split':200,'model':'Fit total seconds T=a+b*N+c*I(N=16) on original200 each question only; derive mean per source as b+a/N+c*I(N=16)/N.','alternatives':['T=b*N','T=a+b*N','T=a+b*N+c*N^2'],'uncertainty':'HC3 covariance and Student-t reference; prediction assessed on new seeds without refitting.','no_causal_claim':'Counts vary with scenes; no claim adding a source in every fixed scene helps.','measurement_identity':'M_disc=m*(20-N)+sum(J_k), S_disc=M_disc-d with0<=d<=m.','binary_sha256':sha(R/'count_profile'),'profile_source_sha256':sha(R/'src/count_profile.cpp')}
(R/'artifacts/design_frozen.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2))
def job(q,split,start):
 out=R/'results'/f'{split}_q{q}.csv';cmd=[str(R/'count_profile'),str(out),str(q),str(start),'200'];begin=time.time();p=subprocess.run(cmd,capture_output=True,text=True)
 record={'command':cmd,'started_unix':begin,'runtime_s':time.time()-begin,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'output':str(out.relative_to(R))}
 if p.returncode==0:record['sha256']=sha(out)
 (R/'artifacts'/f'run_{split}_q{q}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));assert p.returncode==0,record
 print(q,split,'complete',flush=True);return record
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 futures=[pool.submit(job,q,s,start) for s,start in [('training_replay',2610001),('validation',2710001)] for q in [3,4]]
 records=[f.result() for f in futures]
(R/'artifacts/execution.json').write_text(json.dumps({'environment':platform.platform(),'records':records},ensure_ascii=False,indent=2))
