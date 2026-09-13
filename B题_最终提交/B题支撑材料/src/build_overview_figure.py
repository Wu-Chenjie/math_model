"""Render the set-state/action/termination overview with mathematical labels."""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
R = Path(__file__).resolve().parents[1]
from matplotlib import font_manager
available_fonts = {font.name for font in font_manager.fontManager.ttflist}
figure_font = next((name for name in ['Heiti TC', 'Microsoft YaHei',
    'Noto Sans CJK SC', 'SimHei', 'FandolHei'] if name in available_fonts), None)
if figure_font is None:
    import subprocess
    font_file = subprocess.check_output(['kpsewhich', 'FandolHei-Regular.otf'],
                                        text=True).strip()
    if not font_file:
        raise RuntimeError('Install a Chinese font or TeX Fandol fonts.')
    font_manager.fontManager.addfont(font_file)
    figure_font = font_manager.FontProperties(fname=font_file).get_name()

plt.rcParams.update({'font.family':figure_font,'font.size':10,
                     'axes.unicode_minus':False,'pdf.fonttype':42})
fig, ax = plt.subplots(figsize=(8.4, 5.6))
fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
ax.set(xlim=(0,100),ylim=(0,100)); ax.axis('off')
rows = [
 (70, '集合状态',
  r'位置多边形 $P_k$ 与历史响应'+'\n'+
  r'正常测向：$P_k\leftarrow P_k\cap W(s,\theta)$'+'\n'+
  r'发现覆盖：历史扫描点 $H_t$ 与未来点 $F_t$',
  '角锥交与凸性\n有理区间认证', '#edf4fa'),
 (38, '动作与时间目标',
  r'$T=L/5+N_s+5N_m+3N_f+5N_c$'+'\n'+
  '有限动作规划、路径调度与安全提前停车\n观测后更新集合，再选择下一动作',
  '计时恒等分解\n同种子配对实验', '#fcf2e5'),
 (6, '发现完成与清除终止',
  r'保证清除：$\rho(P)\leq20$ 米，清除点属于 $\mathcal{C}(P)$'+'\n'+
  '完成规定扫描或已发现16源后结束发现\n已知源全部清除后退出；光学覆盖提供后备',
  '连续覆盖充分条件\n逐局完成性检查', '#edf6ef')]
for y,title,body,evidence,color in rows:
 for x,w,c in [(5,66,color),(76,22,'#f4f4f4')]:
  ax.add_patch(FancyBboxPatch((x,y),w,26,boxstyle='round,pad=.4',
                            facecolor=c,edgecolor='#63767c',linewidth=.9))
 ax.text(8,y+22,title,weight='bold',va='top',fontsize=12)
 ax.text(8,y+15,body,va='top',linespacing=1.65,fontsize=10)
 ax.text(78,y+22,'论证依据',va='top',weight='bold',fontsize=11)
 ax.text(78,y+14,evidence,va='top',linespacing=1.9,fontsize=10)
 ax.annotate('',(75.5,y+13),(71.5,y+13),arrowprops={'arrowstyle':'->','color':'#63767c'})
for upper,lower in [(70,64),(38,32)]:
 ax.annotate('',(38,lower+.4),(38,upper-.4),arrowprops={'arrowstyle':'->','color':'#63767c'})
for extension in ['pdf','png']:
 fig.savefig(R/'figures'/f'system_overview.{extension}',dpi=180)
plt.close(fig)
