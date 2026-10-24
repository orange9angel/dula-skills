"""Deterministic crop/registration of reviewed atlas cels, with source receipts.

This is layout preparation, not image generation or semantic pose validation.
Coordinates and optional uniform scale/paste anchors must be visually reviewed.
"""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--episode',type=Path,required=True);p.add_argument('--config',required=True);a=p.parse_args()
    cfg=json.loads((a.episode/a.config).read_text(encoding='utf-8'));rows=[]
    for item in cfg['items']:
        source=a.episode/item['source'];im=Image.open(source).convert('RGBA')
        if 'crop' in item:im=im.crop(item['crop'])
        if 'size' in item:im=im.resize(tuple(item['size']),Image.Resampling.LANCZOS)
        if 'luminanceAlpha' in item:
            # Explicitly cropped surface detail only; never infer character masks.
            rgba=np.array(im);spec=item['luminanceAlpha'];rgb=rgba[:,:,:3].astype(float)
            lum=rgb@np.array([.2126,.7152,.0722]);weight=np.clip((spec['ceiling']-lum)/spec['range'],0,1)
            yy,xx=np.mgrid[:im.height,:im.width];edge=np.minimum.reduce([xx,yy,im.width-1-xx,im.height-1-yy]);weight*=np.clip(edge/spec.get('feather',8),0,1)
            rgba[:,:,3]=np.uint8(rgba[:,:,3]*weight);im=Image.fromarray(rgba)
        if 'canvas' in item:
            out=Image.new('RGBA',tuple(item['canvas']));out.alpha_composite(im,tuple(item.get('position',[0,0])));im=out
        target=a.episode/item['output'];target.parent.mkdir(parents=True,exist_ok=True);im.save(target)
        rows.append({'output':item['output'],'size':im.size,'alphaBounds':im.getchannel('A').point(lambda x:255 if x>32 else 0).getbbox(),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    (a.episode/cfg['report']).write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps({'cels':len(rows),'report':cfg['report']}))

if __name__=='__main__':main()
