"""Strip incidental metadata without changing page content or source results."""
from pathlib import Path
from pypdf import PdfReader,PdfWriter
R=Path(__file__).resolve().parents[1]
for source,target,title in [(R/'paper/main.pdf',R/'B题几何策略优化_论文.pdf','有界测向误差下干扰源的连续几何规划与清除'),(R/'B题几何策略优化_题解.pdf',R/'B题几何策略优化_题解.pdf','B题几何策略优化题解与计算交接')]:
 reader=PdfReader(source);writer=PdfWriter();writer.clone_document_from_reader(reader);writer.metadata=None
 writer.add_metadata({'/Title':title,'/Author':'','/Creator':'LaTeX','/Producer':'XeLaTeX'})
 tmp=target.with_suffix('.tmp.pdf')
 with tmp.open('wb') as f:writer.write(f)
 check=PdfReader(tmp);assert len(check.pages)==len(reader.pages)
 assert all(a.get_contents().get_data()==b.get_contents().get_data() for a,b in zip(reader.pages,check.pages))
 tmp.replace(target);print(target.name,len(check.pages),'pages; page streams unchanged')
