"""Pandoc uses authored Markdown and actual generated figures; no new content."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def run(args):
    r=subprocess.run(args,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (ROOT/'results'/('build_'+('pdf'if '.pdf' in ' '.join(args) else 'docx')+'.log')).write_text(r.stdout,encoding='utf-8')
    if r.returncode:raise RuntimeError(r.stdout)
name='B题鲁棒优化_论文交接'
run(['pandoc',name+'.md','-o',name+'.docx','--standalone'])
run(['pandoc',name+'.md','-o',name+'.pdf','--standalone','--pdf-engine=xelatex',
     '-H','src/pdf_header.tex','-V','mainfont=Times New Roman','-V','CJKmainfont=SimSun',
     '-V','CJKsansfont=Microsoft YaHei','-V','CJKmonofont=SimSun'])
print('DOCX and PDF compiled')
