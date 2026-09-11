"""Read-only final-PDF text, page and geometry checks; visual review is separate."""
from pathlib import Path
import hashlib
import json
import re
import sys
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]


def main(path):
    errors=[];pages=[]
    with pdfplumber.open(path) as pdf:
        for i,p in enumerate(pdf.pages):
            text=p.extract_text() or ''
            if not text.strip():errors.append(f'blank_page:{i+1}')
            if abs(p.width-595.276)>1 or abs(p.height-841.89)>1:errors.append(f'not_A4:{i+1}')
            for token in ('内部排版稿','年度结果尚待','尚未填入','??','\ufffd','/Users/'):
                if token in text:errors.append(f'forbidden_token:{i+1}:{token}')
            chars=p.chars
            outside=[c for c in chars if c['x0']<0 or c['x1']>p.width+.2 or c['top']<0 or c['bottom']>p.height+.2]
            if outside:errors.append(f'characters_outside_page:{i+1}')
            footer=''.join(c['text'] for c in chars if c['top']>p.height-60).strip()
            if str(i+1) not in footer:errors.append(f'page_number_missing:{i+1}')
            pages.append({'page':i+1,'width_pt':p.width,'height_pt':p.height,'characters':len(chars),'footer_text':footer})
        full='\n'.join(p.extract_text() or '' for p in pdf.pages)
        if '关键词' not in (pdf.pages[0].extract_text() or ''):errors.append('abstract_not_on_first_page')
        if len(pdf.pages)>30:errors.append('page_count_above_conservative_body_limit30')
    result={'status':'PASS' if not errors else 'FAIL','scope':'Automated checks only; every rendered final page still needs visual inspection.',
        'pdf':str(path.relative_to(ROOT)),'pdf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':pages,'errors':errors}
    (ROOT/'review/pdf-automated-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'pages':len(pages),'errors':errors},ensure_ascii=False))
    raise SystemExit(1 if errors else 0)


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
