"""Independent original Python simulator kernel + real HTTP tests of C++ solver."""
import argparse
import json
import sys
import threading
import time
from pathlib import Path
from bridge import ROOT, drive, DeadlineClient
from mocksim.arena import Session, make_case
from mocksim.client import RobotClient
from mocksim.server import MockSimulator, serve

class KernelClient:
    def __init__(self, problem, seed):
        self.session = Session(make_case(problem=problem, seed=seed))
    def enter(self):
        self.session.enter()
        return dict(accepted=True, remaining_real_duration_s=1200)
    def measure(self,x,y,k):
        o=self.session.measure(x,y,k)
        return dict(accepted=True, virtual_time_s=o.virtual_time_s, **o.payload)
    def clear(self,x,y,k):
        o=self.session.clear(x,y,k)
        return dict(accepted=True, virtual_time_s=o.virtual_time_s, **o.payload)
    def exit(self):
        o=self.session.exit()
        return dict(accepted=True, virtual_time_s=o.virtual_time_s)

def main():
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=30);p.add_argument('--early',type=float,default=35)
    a=p.parse_args();rows=[]
    for problem in [3,4]:
        for seed in range(20001,20001+a.count):
            client=KernelClient(problem,seed)
            out=drive(problem,client,a.early)
            assert out['cleared']==client.session.case.total
            rows.append(dict(layer='original_kernel',problem=problem,seed=seed,**client.session.statistics(out['runtime_s']),certificate=out['certificate']))
        for seed in [30001,30002,30003]:
            sim=MockSimulator(problem=problem,mode='practice',seed=seed,team_id='LOCAL_RESEARCH',port=0)
            server=serve(sim);threading.Thread(target=server.serve_forever,daemon=True).start();sim.start()
            file=ROOT/'results'/f'LOCAL_HTTP_P{problem}_{seed}.jsonl'
            try:
                with file.open('w',encoding='utf-8') as f:
                    client=DeadlineClient(base_url=f'http://127.0.0.1:{server.server_address[1]}',robot_id='LOCAL_RESEARCH',log_sink=lambda r:f.write(json.dumps(r,ensure_ascii=False)+'\n'))
                    out=drive(problem,client,a.early)
                assert out['cleared']==sim.case.total
                rows.append(dict(layer='local_HTTP',problem=problem,seed=seed,total=sim.case.total,**out))
            finally:
                server.shutdown();server.server_close()
    (ROOT/'results'/'original_mock_validation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'validated {len(rows)} original simulator cases (including 6 HTTP runs)')

if __name__=='__main__':main()
