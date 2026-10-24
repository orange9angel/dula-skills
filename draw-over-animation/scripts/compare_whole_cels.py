"""Experimental diagnostic: held complete drawings vs. two rendered motions.

Only uniform scale and translation register a drawing; no limbs are cut or bent.
The tracking camera comparison does not validate planted feet in a scene.
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from propagate_keypaint import register

def main():
    p=argparse.ArgumentParser();p.add_argument('--episode',type=Path,required=True);p.add_argument('--config',required=True);a=p.parse_args()
    cfg=json.loads((a.episode/a.config).read_text(encoding='utf-8'))
    root=a.episode;motion=root/cfg['motion'];baseline=root/cfg['baseline'];out=root/cfg['output'];out.mkdir(parents=True,exist_ok=True)
    for name in ['frames','cels']:(out/name).mkdir(exist_ok=True)
    capture=json.loads((motion/'capture.json').read_text(encoding='utf-8'));keys=capture['config']['keys'];drawings={};registration=[]
    for k in keys:
        art=cfg['art'][k['id']];sheet=np.array(Image.open(root/art['file']).convert('RGBA'));w=sheet.shape[1]//art['columns'];h=sheet.shape[0]//art['rows'];x=art['cell']%art['columns']*w;y=art['cell']//art['columns']*h
        mask=np.array(Image.open(motion/(k['id']+'_mask.png')).convert('L'))
        rgba,record=register(sheet[y:y+h,x:x+w],mask);drawings[k['id']]=rgba;registration.append({'key':k['id'],**record})
        rgb=rgba[:,:,:3]+(1-rgba[:,:,3:4])*np.array([128,136,144])/255
        Image.fromarray(np.uint8(np.clip(rgb*255,0,255))).save(out/'cels'/(k['id']+'.png'))
    font=ImageFont.truetype(cfg['font'],21);small=ImageFont.truetype(cfg['font'],16);records=[]
    for row in capture['rows']:
        tag=f"{row['i']:04d}";key=min(keys,key=lambda k:abs(k['t']-row['t']));art=Image.open(out/'cels'/(key['id']+'.png'));w,h=art.size
        comp=Image.new('RGB',(w*3,h+74),'#18212f')
        for j,im in enumerate([Image.open(baseline/(tag+'_guide.png')),Image.open(motion/(tag+'_guide.png')),art]):comp.paste(im,(j*w,44))
        d=ImageDraw.Draw(comp)
        for j,label in enumerate(cfg['labels']):d.text((j*w+12,10),label,font=font,fill='white')
        d.text((12,h+49),f"诊断机位 / {row['t']:.3f}s / 完整原画 {key['id']} / 尚未通过动态验收",font=small,fill='#ffcf8a')
        comp.save(out/'frames'/(tag+'.png'));records.append({'i':row['i'],'t':row['t'],'key':key['id']})
    (out/'report.json').write_text(json.dumps({'status':'experimental_unapproved','registration':registration,'exposure':records,'limitation':'Nearest complete cels with uniform registration; no interpolation, root travel or world contact claim.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'frames':len(records),'keys':len(drawings),'output':str(out)}))

if __name__=='__main__':main()
