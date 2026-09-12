from pathlib import Path
import json,subprocess
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[2]
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
for old in (P/'tmp/pdfs/storage-final').glob('page-*.png'):old.unlink()
out=P/'tmp/pdfs/storage-final';out.mkdir(parents=True,exist_ok=True)
subprocess.run(['pdftoppm','-scale-to','1000','-png',str(P/'main.pdf'),str(out/'page')],check=True)
files=sorted(out.glob('page-*.png'));assert files
findings=[];bounds=[]
for i,f in enumerate(files,1):
    im=Image.open(f).convert('RGB');a=np.array(im);h,w=a.shape[:2]
    ink=(a.min(2)<160);ink[int(.93*h):]=False
    ys,xs=np.where(ink)
    box={'page':i,'x_min':int(xs.min()),'x_max':int(xs.max()),'y_min':int(ys.min()),'y_max':int(ys.max()),'width':w,'height':h};bounds.append(box)
    if xs.min()<w*25/210-3 or xs.max()>w*185/210+3 or ys.min()<h*25/297-3 or ys.max()>h*272/297+3:findings.append(box)
for n in range(0,len(files),12):
    canvas=Image.new('RGB',(1200,1365),'#dddddd');d=ImageDraw.Draw(canvas)
    for j,f in enumerate(files[n:n+12]):
        im=Image.open(f).convert('RGB');im.thumbnail((292,420));x=(j%4)*300+(300-im.width)//2;y=(j//4)*455+27
        canvas.paste(im,(x,y));d.text(((j%4)*300+10,(j//4)*455+7),str(n+j+1),fill='black')
    canvas.save(out/f'contact-{n//12+1:02}.jpg',quality=91)
dump(P/'review/storage-raster-margins.json',{'pages':len(files),'scale_to':1000,'pixel_tolerance':3,'ink_threshold':160,'footer_exclusion_fraction':.93,'findings':findings,'bounds':bounds,'scope':'Raster screen for page ink outside25mm A4 margins; visual review is a separate required step.'})
subprocess.run(['pdftotext',str(P/'main.pdf'),str(out/'main.txt')],check=True)
print(json.dumps({'pages':len(files),'raster_outliers':len(findings),'contact_sheets':(len(files)+11)//12}),flush=True)
