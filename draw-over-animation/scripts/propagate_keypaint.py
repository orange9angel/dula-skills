"""Experimental whole-cel propagation using renderer-supplied surface maps.

This does not infer unseen artwork. Keep the validity/coverage report and review
the rendered sequence; blending two art keys may still produce double contours.
The first full-body walking trial FAILED visually: registration errors, holes,
double limbs. Do not use it as an approved automatic inbetweener.
"""
import argparse,json
from pathlib import Path
import numpy as np
import cv2
from scipy.ndimage import distance_transform_edt
from PIL import Image,ImageDraw,ImageFont

def bounds(mask):
    y,x=np.where(mask);return x.min(),y.min(),x.max(),y.max()

def register(art,mask):
    a=art[:,:,3]>128;b=mask>127
    ax,ay,ar,ab=bounds(a);bx,by,br,bb=bounds(b)
    scale=(bb-by)/(ab-ay)
    aa=a.copy();aa[int(ay+(ab-ay)*.19):]=False
    ba=b.copy();ba[int(by+(bb-by)*.19):]=False
    tx=np.where(ba)[1].mean()-np.where(aa)[1].mean()*scale;ty=by-ay*scale
    matrix=np.array([[scale,0,tx],[0,scale,ty]],np.float32)
    rgba=art.astype(np.float32)/255;rgba[:,:,:3]*=rgba[:,:,3:4]
    result=cv2.warpAffine(rgba,matrix,(mask.shape[1],mask.shape[0]),flags=cv2.INTER_LINEAR)
    return result,{'scale':float(scale),'translation':[float(tx),float(ty)]}

def warp(art,file,mask,padding):
    im=np.array(Image.open(file).convert('RGB')).astype(np.int32);h,w=mask.shape
    x=im[:,:,0]*16+im[:,:,1]//16;y=(im[:,:,1]%16)*256+im[:,:,2];valid=(x>0)&(y>0)
    xx,yy=np.meshgrid(np.arange(w),np.arange(h));mx=(x-1)/4094*w-.5;my=(y-1)/4094*h-.5
    dist,nearest=distance_transform_edt(~valid,return_indices=True)
    extended=(~valid)&(mask<128)&(dist<=padding)
    dx=mx-xx;dy=my-yy
    mx[extended]=xx[extended]+dx[tuple(nearest[:,extended])];my[extended]=yy[extended]+dy[tuple(nearest[:,extended])]
    valid|=extended
    out=cv2.remap(art,mx.astype(np.float32),my.astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    out*=valid[:,:,None]
    return out,valid

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--atlas',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--columns',type=int,default=2);ap.add_argument('--rows',type=int,default=2);ap.add_argument('--edge-padding',type=int,default=28);a=ap.parse_args()
    capture=json.loads((a.capture/'capture.json').read_text(encoding='utf-8'));cfg=capture['config'];sheet=np.array(Image.open(a.atlas).convert('RGBA'));cw=sheet.shape[1]//a.columns;ch=sheet.shape[0]//a.rows
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'frames').mkdir(exist_ok=True);(a.output/'rgba').mkdir(exist_ok=True)
    keys=[];registrations=[]
    for k in cfg['keys']:
        x=(k['cell']%a.columns)*cw;y=(k['cell']//a.columns)*ch;art=sheet[y:y+ch,x:x+cw];mask=np.array(Image.open(a.capture/(k['id']+'_mask.png')).convert('L'))
        registered,record=register(art,mask);keys.append(registered);registrations.append({'id':k['id'],**record})
        rgb=registered[:,:,:3]+(1-registered[:,:,3:4])*np.array([128,136,144])/255
        Image.fromarray(np.uint8(np.clip(rgb*255,0,255))).save(a.output/(k['id']+'_registered.png'))
    records=[];font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22)
    for row in capture['rows']:
        i=row['i'];tag=f'{i:04d}';lo,hi=row['lo'],row['hi'];mask=np.array(Image.open(a.capture/(tag+'_mask.png')).convert('L'))
        left,lv=warp(keys[lo],a.capture/(tag+'_to_'+cfg['keys'][lo]['id']+'.png'),mask,a.edge_padding)
        right,rv=warp(keys[hi],a.capture/(tag+'_to_'+cfg['keys'][hi]['id']+'.png'),mask,a.edge_padding)
        u=0 if lo==hi else np.clip((row['t']-cfg['keys'][lo]['t'])/(cfg['keys'][hi]['t']-cfg['keys'][lo]['t']),0,1)
        # Normalize per-pixel only where one reference is occluded; preserve
        # authored transparency where both references are available.
        wl=(1-u)*lv;wr=u*rv;den=wl+wr;out=(left*wl[:,:,None]+right*wr[:,:,None])/np.maximum(den[:,:,None],1e-8)
        rgba=out.copy();rgba[:,:,:3]/=np.maximum(rgba[:,:,3:4],1e-8);Image.fromarray(np.uint8(np.clip(rgba*255,0,255))).save(a.output/'rgba'/(tag+'.png'))
        rgb=out[:,:,:3]+(1-out[:,:,3:4])*np.array([128,136,144])/255;paint=Image.fromarray(np.uint8(np.clip(rgb*255,0,255)))
        source=Image.open(a.capture/(tag+'_guide.png')).convert('RGB');w,h=source.size
        comp=Image.new('RGB',(w*2,h));comp.paste(source,(0,0));comp.paste(paint,(w,0));d=ImageDraw.Draw(comp);d.rectangle((0,0,w*2,42),fill='#18212f');d.text((14,8),'真人动作参考 → 原3D外形',font=font,fill='white');d.text((w+14,8),'同一动作 → 生成原画轮廓',font=font,fill='white');comp.save(a.output/'frames'/(tag+'.png'))
        inside=mask>127;records.append({'frame':i,'t':row['t'],'referenceCoverage':float(np.mean((lv|rv)[inside])),'fractionOfProxyWithPaint':float(np.mean((out[:,:,3]>.5)[inside]))})
    (a.output/'report.json').write_text(json.dumps({'config':vars(a)|{'capture':str(a.capture),'atlas':str(a.atlas),'output':str(a.output)},'registration':registrations,'frames':records,'limitation':'Coverage is not an artistic pass; silhouettes intentionally differ from proxy.'},indent=2),encoding='utf-8');print(json.dumps({'frames':len(records),'minimumReferenceCoverage':min(r['referenceCoverage'] for r in records)}))

if __name__=='__main__':main()
