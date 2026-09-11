"""Final document/data cross-check; run using the bundled document Python."""
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'B题_论文撰写交接.md').read_text(encoding='utf-8')
assert '{{'not in text and '最终模拟评分与文字证据审查正在进行'not in text
assert '91/100'in text and '87.7104'in text
for required in ['349.87','868.17','950.708979','968.901572','315757.6','537','540','108']:
    assert required in text,required
summary=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
for p in ['3','4']:
    assert summary['main'][p]['case_full_success']['success']==200
    assert summary['main'][p]['case_full_success']['total']==200
    assert f"{summary['main'][p]['avg_s']['mean']:.2f}"in text
mock=json.loads((ROOT/'results/original_mock_validation.json').read_text(encoding='utf-8'))
assert len(mock)==66
for row in mock:
    if row['layer']=='local_HTTP':
        assert f"{row['runtime_s']:.2f}"in text
        assert row['cleared']==row['total']
        logs=[json.loads(s)for s in (ROOT/'results'/f"LOCAL_HTTP_P{row['problem']}_{row['seed']}.jsonl").read_text(encoding='utf-8').splitlines()]
        assert logs[0]['path']=='/enter'and logs[-1]['path']=='/exit'
        assert all(x['path']in ['/enter','exit','/exit','/measure','/clear']and x['http_status']==200 for x in logs)
for p in [3,4]:
    final=[r for r in csv.DictReader((ROOT/'results/final_smoke.csv').open())if int(r['problem'])==p][0]
    old=[r for r in csv.DictReader((ROOT/'results/test_main.csv').open())if int(r['problem'])==p and int(r['seed'])==10001][0]
    for key in ['time_s','cleared','measures','miss','certificate']:assert final[key]==old[key],key
with ZipFile(ROOT/'B题_论文撰写交接.docx')as z:
    xml=z.read('word/document.xml');tree=ET.fromstring(xml)
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    equations=len(tree.findall('.//m:oMath',ns));assert equations>=60
    drawings=len(tree.findall('.//w:drawing',ns));assert drawings>=5
pdf=PdfReader(ROOT/'B题_论文撰写交接.pdf')
assert 15<=len(pdf.pages)<=30
alltext=''.join(p.extract_text()for p in pdf.pages)
for required in ['349.87','868.17','91/100','950.708979']:
    assert required in alltext,required
for fig in range(1,6):
    for suffix in ['png','svg','pdf']:assert list((ROOT/'figures').glob(f'图{fig}_*.{suffix}'))
out={'status':'passed','pdf_pages':len(pdf.pages),'docx_math_objects':equations,'docx_drawings':drawings,
     'main_cases':400,'stress_cases':1000,'original_mock_cases':66,'official_formal_cases':0,
     'final_solver_smoke_matches_frozen_cases':True,'markdown_pdf_docx_and_results_consistent':True}
(ROOT/'review/final_artifact_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
