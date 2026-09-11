"""Compile the verified-result manuscript and render every final PDF page."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from current_evidence import require_paper_sources_current

ROOT=Path(__file__).resolve().parents[1]
TEX=Path('/Library/TeX/texbin/xelatex')
PY=Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
FINAL=ROOT/'output/pdf/微网跨日随机控制.pdf'


def main():
    start=time.perf_counter()
    proof=json.loads((ROOT/'artifacts/paper-results.json').read_text());assert proof['status']=='verified'
    require_paper_sources_current(ROOT,proof)
    for name in ('abstract','results','discussion','appendix'):
        assert (ROOT/f'paper/generated/{name}.tex').is_file()
    tex_files=[ROOT/'paper/main.tex',*sorted((ROOT/'paper/generated').glob('*.tex'))]
    for file in tex_files:
        content=file.read_text()
        expressions=re.findall(r'\\\[(.*?)\\\]|\\\((.*?)\\\)|(?<!\\)\$(.*?)(?<!\\)\$',content,re.S)
        blocks=re.findall(r'\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}(.*?)\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}',content,re.S)
        assert not any(re.search('[\u4e00-\u9fff]',s) for parts in expressions for s in parts),f'Chinese inside inline math: {file}'
        assert not any(re.search('[\u4e00-\u9fff]',s) for s in blocks),f'Chinese inside display math: {file}'
    temp=ROOT/'tmp/pdfs/final';temp.mkdir(parents=True,exist_ok=True)
    for pass_number in range(3):
        with (temp/f'compile-{pass_number+1}.log').open('w') as log:
            p=subprocess.run([str(TEX),'-interaction=nonstopmode','-halt-on-error',f'-output-directory={temp}','main.tex'],cwd=ROOT/'paper',stdout=log,stderr=subprocess.STDOUT)
        if p.returncode:raise RuntimeError(f'LaTeX failed, inspect {temp}')
    log=(temp/'main.log').read_text(errors='replace')
    errors=[line for line in log.splitlines() if any(token in line for token in ('Overfull','Missing character','undefined references','undefined on input','LaTeX Error'))]
    if errors:raise RuntimeError('Typesetting errors: '+repr(errors))
    FINAL.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(temp/'main.pdf',FINAL)
    render=temp/'pages';render.mkdir(exist_ok=True)
    for old in render.glob('page-*.png'):old.unlink()
    p=subprocess.run(['/opt/homebrew/bin/pdftoppm','-r','140','-png',str(FINAL),str(render/'page')])
    if p.returncode:raise RuntimeError('PDF rendering failed')
    p=subprocess.run([str(PY),'tools/check_paper_pdf.py',str(FINAL)],cwd=ROOT)
    if p.returncode:raise RuntimeError('PDF automated QA failed')
    record={'status':'compiled_and_rendered_visual_review_pending','command':sys.argv,'exit_code':0,
        'runtime_seconds':time.perf_counter()-start,'pdf':str(FINAL.relative_to(ROOT)),
        'pdf_sha256':hashlib.sha256(FINAL.read_bytes()).hexdigest(),
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tex_files},
        'figure_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'figures').glob('*.png'))},
        'rendered_pages':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(render.glob('page-*.png'))}}
    (ROOT/'artifacts/pdf-build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
