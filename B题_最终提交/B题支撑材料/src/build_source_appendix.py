"""Regenerate paper/source_appendix.tex from the current source inventory.

Appendix B lists all shipped source files and writes the shared source count.
The build pipeline preserves reviewed numerical tables and their comparisons.
"""
from pathlib import Path

R = Path(__file__).resolve().parents[1]
P = R / 'paper'

source_roots = [R / 'src', R / 'tests', R / 'review',
                R / 'supplement/count_time/src', R / 'supplement/count_time_theory/src',
                R / 'vendor/mocksim']
source_ext = {'.py', '.cpp', '.hpp', '.h', '.c', '.cc'}

files = []
for base in source_roots:
    if base.exists():
        files.extend(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in source_ext)
files.append(R / 'run_all.py')
files = sorted(set(files), key=lambda p: p.relative_to(R).as_posix())

tex = (r'\section{完整计算源程序}\small 此附录列出在线机器人、实验内核、消融模块、'
       r'几何证书与附加分析脚本的完整源码；共' + str(len(files)) +
       r'个文件，与支撑包内文件逐项对应。历史方法分支仅供复核，不表示默认启用。'
       r'模块标题与支撑包同名。' + '\n')
for path in files:
    rel = path.relative_to(R).as_posix()
    title = rel.replace('_', r'\_')
    if rel == 'run_all.py':
        tex += r'\clearpage' + '\n'
    tex += (r'\subsection*{\texttt{' + title + r'}}' + '\n' +
            r'\lstinputlisting[basicstyle=\ttfamily\fontsize{8}{9.5}\selectfont,'
            r'breaklines=true,breakatwhitespace=false,columns=fullflexible,'
            r'keepspaces=true,numbers=left,numberstyle=\tiny,numbersep=3pt]{../' + rel + '}\n')

(P / 'source_appendix.tex').write_text(tex, encoding='utf-8')
print('source_appendix.tex regenerated with', len(files), 'modules')

(P / "source_count.tex").write_text(r"\newcommand{\SourceFileCount}{" + str(len(files)) + "}\n", encoding="utf-8")
