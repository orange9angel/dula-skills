"""Pack same-image source crops for one local-edit request, with exact provenance.
This slices/tiles pixels only; it never redraws faces or synthesizes expressions.
"""
import argparse,json
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=json.loads(a.config.read_text(encoding='utf-8'));w,h=c['cell'];cols=c['columns'];rows=(len(c['targets'])+cols-1)//cols
atlas=Image.new('RGBA',(w*cols,h*rows));mapping=[]
for i,t in enumerate(c['targets']):
 im=Image.open(a.config.parent/t['source']).convert('RGBA');x,y,tw,th=t['crop']
 if (tw,th)!=(w,h):raise ValueError('Use native pixels: every crop must match cell size')
 ox=i%cols*w;oy=i//cols*h;atlas.alpha_composite(im.crop((x,y,x+w,y+h)),(ox,oy));mapping.append({**t,'atlas':[ox,oy,w,h]})
a.output.parent.mkdir(parents=True,exist_ok=True);atlas.save(a.output)
a.output.with_suffix('.json').write_text(json.dumps({'size':list(atlas.size),'targets':mapping},indent=2),encoding='utf-8')
print(f'{len(mapping)} native same-image crops; {atlas.size}')
