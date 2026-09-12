from pathlib import Path
import json,re,hashlib
import pdfplumber
O=Path(__file__).resolve().parents[1];p=O/'revised-main.pdf'
with pdfplumber.open(p) as doc:
 pages=[{'page':i+1,'width':float(q.width),'height':float(q.height),'text_chars':len(q.extract_text() or '')} for i,q in enumerate(doc.pages)]
 first=doc.pages[0].extract_text() or '';second=doc.pages[1].extract_text() or '';text='\n'.join(q.extract_text() or '' for q in doc.pages)
 assert '摘要' in first.replace(' ','') and '关键词' in first
 assert '问题重述与控制视角' in second
 assert all(abs(q['width']-595.276)<1 for q in pages)
 assert '/Users/' not in text and 'wuchenjie' not in text.lower()
 assert '??' not in text[:text.find('支撑文件与完整源程序')]
source=(O/'revised-main.tex').read_text()+'\n'+(O/'technical-appendix.tex').read_text()
pattern=r'\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]|\\begin\{(equation\*?|align\*?)\}.*?\\end\{\1\}'
hits=[]
for m in re.finditer(pattern,source,re.S):
 if re.search('[\u4e00-\u9fff]',m.group()):hits.append(m.group()[:160])
assert not hits,hits
log=(O/'revised-main.log').read_text(errors='replace');errors=[x for x in ['Overfull','Missing character','undefined references','undefined on input'] if x in log]
assert not errors,errors
end=int(re.search(r'\\newlabel\{bodyend\}\{\{10\}\{(\d+)\}',(O/'revised-main.aux').read_text()).group(1))
result={'pages':len(pages),'abstract_pages':1,'body_pages_including_references':end-1,'appendix_pages':len(pages)-end,'page_size':'A4','declared_margins_mm':25,'page_numbering':'plain footer center','pdf_bytes':p.stat().st_size,'pdf_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'math_chinese_hits':hits,'latex_issues':errors,'anonymity_path_checks':'passed','page_text_counts':pages,'visual_review':'Final PNG pages and workbook views reviewed separately; see final-review.md'}
assert end-1<=30 and p.stat().st_size<20*1024**2
(O/'artifacts/pdf-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='page_text_counts'},ensure_ascii=False))
