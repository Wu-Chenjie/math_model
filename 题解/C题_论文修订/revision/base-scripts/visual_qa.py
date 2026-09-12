from pathlib import Path
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parents[1]
ps=sorted((O/'tmp/pdfs').glob('all-*.png'))
for start in range(0,len(ps),8):
 c=Image.new('RGB',(1200,1700),'#ddd');d=ImageDraw.Draw(c)
 for j,p in enumerate(ps[start:start+8]):
  im=Image.open(p);im.thumbnail((580,395));x=(j%2)*600;y=(j//2)*425;c.paste(im,(x,y+20));d.text((x+4,y+2),p.stem,fill='black')
 c.save(O/f'tmp/pdfs/contact-{start//8}.png')
ps=sorted((O/'artifacts/previews').glob('after-*.png'))
for start in range(0,len(ps),6):
 c=Image.new('RGB',(1500,1350),'white');d=ImageDraw.Draw(c)
 for j,p in enumerate(ps[start:start+6]):
  im=Image.open(p);im.thumbnail((740,415));x=(j%2)*750;y=(j//2)*450;c.paste(im,(x,y+22));d.text((x+4,y+2),p.stem,fill='black')
 c.save(O/f'tmp/pdfs/xlsx-contact-{start//6}.png')
