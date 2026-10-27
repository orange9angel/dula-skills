"""Split a regular RGBA pose atlas, retaining real alpha and registering margins.

This is production slicing, not redrawing or changing any depicted anatomy.
"""
from pathlib import Path
import argparse,json
from PIL import Image
import numpy as np
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--columns',type=int,required=True);p.add_argument('--rows',type=int,required=True);p.add_argument('--sequence');p.add_argument('--width',type=int,default=384);p.add_argument('--height',type=int,default=512);p.add_argument('--figure-height',type=int,default=480);a=p.parse_args()
im=Image.open(a.source).convert('RGBA');cw=im.width/a.columns;ch=im.height/a.rows
if a.figure_height>a.height:raise ValueError('Figure height exceeds canvas')
order=list(map(int,a.sequence.split(','))) if a.sequence else list(range(a.columns*a.rows));a.output.mkdir(parents=True,exist_ok=True);cells=[]
for i,k in enumerate(order):
 if not 0<=k<a.columns*a.rows:raise ValueError('Atlas index out of range')
 src=im.crop((round(k%a.columns*cw),round(k//a.columns*ch),round((k%a.columns+1)*cw),round((k//a.columns+1)*ch)))
 yy,xx=np.where(np.asarray(src.getchannel('A'))>40)
 if not len(xx):raise ValueError(f'Empty pose {k}')
 fig=src.crop((int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)));scale=a.figure_height/fig.height
 fig=fig.resize((round(fig.width*scale),a.figure_height),Image.Resampling.LANCZOS)
 if fig.width>a.width:raise ValueError(f'Pose {k} exceeds target width')
 out=Image.new('RGBA',(a.width,a.height));out.alpha_composite(fig,((a.width-fig.width)//2,(a.height-a.figure_height)//2));out.save(a.output/f'walk_{i}.png');cells.append({'alpha_bbox':list(out.getbbox()),'atlas_index':k})
(a.output/'walk_cells.json').write_text(json.dumps({'cells':cells},indent=2),encoding='utf-8');print(f'{len(order)} registered exposures from {a.columns*a.rows} original poses')
