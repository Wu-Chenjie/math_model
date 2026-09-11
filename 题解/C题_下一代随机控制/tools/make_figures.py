"""Publication-size structural and computed closed-loop figures."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties
from compare_incremental_results import daily_ledger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nextgen_scenarios import Config
FONT = FontProperties(fname='/System/Library/Fonts/Supplemental/Songti.ttc')
plt.rcParams.update({'font.family': FONT.get_name(), 'font.size': 9,
    'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.linewidth': .7, 'xtick.direction': 'out', 'ytick.direction': 'out',
    'savefig.dpi': 350, 'svg.fonttype': 'path'})
OUT = ROOT/'figures'; OUT.mkdir(exist_ok=True)
COLORS = ['#21618C', '#D68910', '#17836B', '#8056A2']


def save(fig, name):
    for ext in ('png', 'svg'): fig.savefig(OUT/(name+'.'+ext), bbox_inches='tight', facecolor='white')
    plt.close(fig)


def structure():
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 4.7))
    texts = [
        ['合法历史与已发布预报', '历史残差完整成熟块\n按时间位置选择代表',
         '因果仿射合同规划\n两午夜时域与线性末值', 'M0：三状态 Markov\n库存凸分段线性价值', '原物理执行器与同一计费器\n跨日连续；真实首末库存一致'],
        ['合法历史与已发布预报', '官方 / 历史融合与在线修正\n当前误差加权 + 联合轨迹缩减',
         '同一因果仿射合同框架\n固定 H 比较；共同状态特征', 'M0 保留；M1 同参数直接对照\n经验创新与凸库存概率反馈', '原物理执行器与同一计费器\n跨日连续；真实首末库存一致']]
    for k, ax in enumerate(axes):
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
        ax.set_title(['冻结旧框架', '增量候选框架'][k], fontsize=12, pad=10)
        for j, label in enumerate(texts[k]):
            y = .84-j*.17
            box = FancyBboxPatch((.06, y-.055), .88, .115, boxstyle='round,pad=0.012,rounding_size=0.015',
                linewidth=.9, edgecolor=COLORS[k], facecolor=['#F2F6FA', '#FBF6EC'][k])
            ax.add_patch(box); ax.text(.5, y, label, ha='center', va='center', fontsize=9, linespacing=1.45)
            if j<4: ax.add_patch(FancyArrowPatch((.5,y-.07),(.5,y-.102),arrowstyle='-|>',mutation_scale=12,color='#55616E',linewidth=1))
    fig.text(.5, .025, '只有 1 月选定模型通过同口径年度账单与独立验证，才替换主模型。', ha='center', fontsize=9)
    fig.subplots_adjust(wspace=.12, bottom=.1, top=.90)
    save(fig, '新旧模型结构')


def results():
    frozen = json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text())
    adopted = json.loads((ROOT/'artifacts/model-adoption.json').read_text())
    assert adopted['status'] == 'PASS'
    challenger = Config(**frozen['challenger']); ids = ['q2', 'q3', 'q4_2', 'q4_3']
    labels = ['问题二', '问题三', '问题四-2', '问题四-3']
    fig, axes = plt.subplots(2, 2, figsize=(6.4, 4.5), sharex=True)
    for ax, kind, label, color in zip(axes.flat, ids, labels, COLORS):
        current = daily_ledger(ROOT/f'artifacts/formal/{kind}_{challenger.identity()}')
        old = daily_ledger(ROOT/f'baseline_frozen/artifacts/global-terminal/{kind}_markov_mpc')
        dates = np.array(current['dates'], dtype='datetime64[D]')
        delta = (old['total_cost']-current['total_cost'])/10000
        ax.plot(dates, np.cumsum(delta), lw=1.5, color=color)
        ax.axhline(0, color='#555555', lw=.65); ax.set_title(label, loc='left', fontsize=10)
        ax.set_ylabel('累计节省 / 万元'); ax.grid(axis='y', alpha=.16)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[2,5,8,11]));ax.xaxis.set_major_formatter(mdates.DateFormatter('%m月'))
    fig.tight_layout()
    save(fig, '挑战模型逐日累计配对差')

    fig, ax = plt.subplots(figsize=(6.3, 2.8))
    rows = adopted['question_results']
    y = np.array([r['saving_yuan']/10000 for r in rows])
    lo = np.array([r['bootstrap_95_lower_yuan']/10000 for r in rows])
    hi = np.array([r['bootstrap_95_upper_yuan']/10000 for r in rows])
    for i in range(4):
        ax.plot([lo[i],hi[i]],[i,i],color=COLORS[i],lw=2)
        ax.scatter([y[i]],[i],color=COLORS[i],s=30,zorder=3)
    ax.axvline(0,color='#555555',lw=.8);ax.set_yticks(range(4),labels);ax.invert_yaxis()
    ax.set_xlabel('全年配对节省 / 万元');ax.grid(axis='x',alpha=.16)
    fig.text(.5,.015,'点为实际全年节省；线为 7 日移动块 bootstrap 的 95% 区间。',ha='center',fontsize=9)
    fig.subplots_adjust(bottom=.23,left=.18,right=.96,top=.96);save(fig,'全年节省与配对区间')

    fig, axes = plt.subplots(2,2,figsize=(6.4,4.4),sharex=True,sharey=True)
    for ax,kind,label,color in zip(axes.flat,ids,labels,COLORS):
        path=ROOT/f'artifacts/formal/{kind}_{challenger.identity()}.npz'
        with np.load(path) as a:
            dates=a['dates'].astype('datetime64[D]');soc=a['state']/12000*100
        ax.fill_between(dates,soc.min(1),soc.max(1),color=color,alpha=.17,label='日内范围')
        ax.plot(dates,soc[:,-1],color=color,lw=.75,label='日末库存')
        ax.axhline(10,color='#777777',lw=.6,ls='--');ax.axhline(90,color='#777777',lw=.6,ls='--')
        ax.set_title(label,loc='left',fontsize=10);ax.set_ylim(5,95);ax.set_ylabel('库存 / 额定容量 %')
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[2,5,8,11]));ax.xaxis.set_major_formatter(mdates.DateFormatter('%m月'))
    axes[0,0].legend(frameon=False,ncol=2,fontsize=9)
    fig.tight_layout();save(fig,'跨日库存与日内范围')

    comparisons=json.loads((ROOT/'artifacts/incremental-comparisons.json').read_text())
    allrows=comparisons['summaries']
    fig,axes=plt.subplots(1,2,figsize=(6.4,3.1))
    for kind,label,color,marker in zip(ids,labels,COLORS,['o','s','^','D']):
        rows=[]
        for h in (48,72,96):
            cid=Config(horizon_hours=h).identity()
            rows.append(next(r for r in allrows if r['kind']==kind and r['configuration_id']==cid and r['comparison']=='fixed48_reference'))
        axes[0].plot([48,72,96],[r['saving_percent'] for r in rows],marker=marker,ms=4,lw=1.2,color=color,label=label)
        axes[1].plot([48,72,96],[r['planning_seconds']/60 for r in rows],marker=marker,ms=4,lw=1.2,color=color,label=label)
    axes[0].set_ylabel('相对固定 48 小时的节省 / %');axes[1].set_ylabel('累计合同 LP 求解时间 / 分钟')
    for ax in axes:ax.set_xticks([48,72,96]);ax.set_xlabel('固定规划时域 / 小时');ax.grid(axis='y',alpha=.16)
    axes[0].axhline(0,color='#777777',lw=.6);axes[0].legend(frameon=False,fontsize=9)
    fig.tight_layout();save(fig,'固定时域收益与计算量')


def main(only_structure):
    start=time.perf_counter();structure()
    if not only_structure:results()
    files=sorted(OUT.glob('*.png'))+sorted(OUT.glob('*.svg'))
    report={'status':'structure_only' if only_structure else 'computed',
        'execution':{'command':sys.argv,'exit_code':0,'runtime_seconds':time.perf_counter()-start},
        'outputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    if not only_structure:
        source_paths=['artifacts/frozen-development-selection.json','artifacts/model-adoption.json','artifacts/incremental-comparisons.json']
        frozen=json.loads((ROOT/source_paths[0]).read_text());cid=Config(**frozen['challenger']).identity()
        source_paths += [f'artifacts/formal/{kind}_{cid}.npz' for kind in ('q2','q3','q4_2','q4_3')]
        report['source_hashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths}
    (ROOT/'artifacts/figure-execution.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--structure-only',action='store_true');main(p.parse_args().structure_only)
