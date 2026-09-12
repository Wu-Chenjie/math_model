from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parents[1];B=R.parent/'C题_跨日随机控制'
for f in ['/System/Library/Fonts/STHeiti Medium.ttc']:
 if Path(f).exists():font_manager.fontManager.addfont(f)
plt.rcParams.update({'font.family':['Heiti TC','Arial Unicode MS','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False})
a=np.load(B/'artifacts/global-terminal/q3_markov_mpc.npz');day=list(a['dates'].astype(str)).index('2025-03-20');x=np.arange(144)/6
fig,axes=plt.subplots(3,1,figsize=(8,5.6),sharex=True,layout='constrained')
axes[0].step(x,a['q'][day],where='post',label='0时合同',lw=1.1,color='#477a9e');axes[0].step(x,a['r'][day],where='post',label='最终合同',lw=1.1,color='#d27f42');axes[0].set_ylabel('合同电量 / kWh');axes[0].legend(ncol=2,loc='upper right')
axes[1].bar(x,a['emergency'][day],width=1/6,align='edge',color='#bc4f4c');axes[1].set_ylabel('紧急电量 / kWh');axes[1].text(.98,.83,'紧急补购发生于09:20–10:00',transform=axes[1].transAxes,ha='right')
axes[2].plot(np.arange(145)/6,a['state'][day]/1000,color='#357c6f');axes[2].set(ylabel='内部库存 / MWh',xlabel='时刻 / h',xlim=(0,24),xticks=np.arange(0,25,3))
for ax in axes:
 ax.grid(axis='y',alpha=.2)
 for t in [6,12,18]:ax.axvline(t,ls=':',lw=.7,color='#999999')
fig.savefig(R/'figures/contracts-revision.png',dpi=200);fig.savefig(R/'figures/contracts-revision.pdf');plt.close(fig)
