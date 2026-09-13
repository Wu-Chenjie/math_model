"""Paired, frozen-method evaluation. This script never selects a controller."""
import argparse
import csv
import json
import math
import statistics as stats
from collections import defaultdict
from pathlib import Path


def interval(values):
    center=stats.mean(values)
    half=1.96*stats.stdev(values)/math.sqrt(len(values)) if len(values)>1 else 0.
    return [center-half,center+half]


def summarize(old,new):
    a=[r['time_s'] for r in old]
    b=[r['time_s'] for r in new]
    differences=[x-y for x,y in zip(a,b)]
    single_old=stats.mean(r['avg_s'] for r in old)
    single_new=stats.mean(r['avg_s'] for r in new)
    ratio=stats.mean(b)/stats.mean(a)
    centered=[y-ratio*x for x,y in zip(a,b)]
    se=stats.stdev(centered)/math.sqrt(len(a))/stats.mean(a) if len(a)>1 else 0.
    cpu=[r['runtime_s'] for r in new]
    return dict(cases=len(old),baseline_total_s=stats.mean(a),candidate_total_s=stats.mean(b),
        total_gain_pct=100*(1-ratio),total_gain_ci95_pct=[100*(1-ratio-1.96*se),100*(1-ratio+1.96*se)],
        baseline_single_s=single_old,candidate_single_s=single_new,single_gain_pct=100*(1-single_new/single_old),
        saving_s_mean=stats.mean(differences),saving_s_ci95=interval(differences),
        wins=sum(x>1e-4 for x in differences),ties=sum(abs(x)<=1e-4 for x in differences),losses=sum(x < -1e-4 for x in differences),
        worst_saving_s=min(differences),best_saving_s=max(differences),cpu_mean_s=stats.mean(cpu),cpu_max_s=max(cpu))


def read_rows(files):
    rows={}
    for file in files:
        with open(file,newline='',encoding='utf-8-sig') as stream:
            for raw in csv.DictReader(stream):
                key=tuple(int(raw[x]) for x in ('problem','seed','stress'))
                if key in rows:raise ValueError(f'duplicate case {key}')
                row=dict(raw)
                for k in ('time_s','avg_s','runtime_s','move_m'):row[k]=float(row[k])
                if int(row['n'])!=int(row['cleared']):raise ValueError(f'incomplete clearance {key}')
                rows[key]=row
    if not rows:raise ValueError('empty input')
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',nargs='+',required=True)
    parser.add_argument('--candidate',nargs='+',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--expected-per-problem',type=int,required=True)
    parser.add_argument('--shortcut-check',action='store_true')
    args=parser.parse_args()
    old,new=read_rows(args.baseline),read_rows(args.candidate)
    if old.keys()!=new.keys():raise ValueError('paired case keys differ')
    if {int(r['method']) for r in old.values()}!={56}:raise ValueError('comparison baseline must be frozen method56')
    methods={int(r['method']) for r in new.values()}
    if len(methods)!=1:raise ValueError('candidate policies must not be pooled')
    groups=defaultdict(list)
    unchanged=('n','cleared','measures','switches','miss','fallbacks','dp_calls','dp_actions','dp_fallbacks','dp_expanded','dp_budget_hits','aux_calls','aux_positive','joint_steps','certificate')
    for key in sorted(old):
        if args.shortcut_check:
            for field in unchanged:
                if old[key][field]!=new[key][field]:raise ValueError(f'controller changed {key}: {field}')
            delta=old[key]['time_s']-new[key]['time_s']
            if delta < -1e-4:raise ValueError(f'shortcut regressed {key}: {delta}')
            if abs(delta-float(new[key]['shortcut_saved_m'])/5)>1e-4:raise ValueError(f'shortcut accounting mismatch {key}')
        groups[(key[0],key[2])].append(key)
    result=dict(baseline_method=56,candidate_method=methods.pop(),paired_cases=len(old),groups={})
    for (problem,stress),keys in groups.items():
        if len(keys)!=args.expected_per_problem:raise ValueError(f'unexpected group count {problem,stress,len(keys)}')
        a,b=[old[k] for k in keys],[new[k] for k in keys]
        row=summarize(a,b)
        row['all_cleared']=True
        row['worst_seed']=keys[min(range(len(keys)),key=lambda i:a[i]['time_s']-b[i]['time_s'])][1]
        row['budget_hits']=sum(int(r['dp_budget_hits']) for r in b)
        row['shortcuts']=sum(int(r.get('shortcuts',0)) for r in b)
        result['groups'][f'p{problem}_stress{stress}']=row
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
