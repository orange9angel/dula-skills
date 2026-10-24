"""Register complete cels by face, pelvis and support height, never silhouette height.

Uses fixed horizontal scale and a continuous vertical remap. No limb segmentation,
joint rotation, cross-fade or generated detail. Author/agent supplies pelvis anchors;
the optional warm-skin face detector is only for a declared compatible palette.
"""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image

def face_center(rgba,roi):
    x0,y0,x1,y1=roi;rgb=rgba[y0:y1,x0:x1,:3].astype(float);r,g,b=rgb.transpose(2,0,1)
    m=((rgba[y0:y1,x0:x1,3]>220)&(r>160)&(g>110)&(r>b*1.15)&(g>b*.95)).astype('uint8')
    n,labels,stats,centers=cv2.connectedComponentsWithStats(m)
    if n<2:raise ValueError('No warm-skin face component; provide an explicit face anchor')
    k=1+np.argmax(stats[1:,cv2.CC_STAT_AREA])
    if stats[k,cv2.CC_STAT_AREA]<80:raise ValueError('Insufficient face evidence')
    return centers[k]+np.array([x0,y0])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--episode',type=Path,required=True);ap.add_argument('--config',required=True);a=ap.parse_args()
    root=a.episode;c=json.loads((root/a.config).read_text(encoding='utf-8'));out=root/c['output'];out.mkdir(parents=True,exist_ok=True)
    w,h=c['size'];fx,fy=c['faceTarget'];hx,hy=c['hipTarget'];ground=c['groundY'];report=[];images={}
    for k in c['cels']:
        sheet=Image.open(root/k['file']).convert('RGBA');cw,ch=sheet.width//k['columns'],sheet.height//k['rows'];x=k['cell']%k['columns']*cw;y=k['cell']//k['columns']*ch
        cel=sheet.crop((x,y,x+cw,y+ch))
        if 'sourceSize' in k:cel=cel.resize(tuple(k['sourceSize']),Image.Resampling.LANCZOS)
        cw,ch=cel.size;s=k.get('scale',c['scale'])
        im=np.array(cel);face=np.array(k['face']) if 'face' in k else face_center(im,c['faceROI']);hip=np.array(k['hip'],float)
        alpha=im[:,:,3].astype(float)/255;core=alpha>c.get('coreAlpha',.86);distance=distance_transform_edt(~core)
        alpha[distance>c.get('edgeAllowance',1.5)]=0
        if c.get('largestComponentOnly',False):
            n,labels,stats,_=cv2.connectedComponentsWithStats((alpha>0).astype('uint8'))
            keep=1+np.argmax(stats[1:,cv2.CC_STAT_AREA]);alpha[labels!=keep]=0;core=(alpha>c.get('coreAlpha',.86))
        lower=np.argwhere(core&(np.arange(ch)[:,None]>hip[1]+60));sole=float(np.quantile(lower[:,0],.999))
        src=np.array([0,face[1],hip[1],sole,ch],float);dst=np.array([fy-face[1]*s,fy,hy,ground,ground+(ch-sole)*s])
        if np.any(np.diff(src)<=0) or np.any(np.diff(dst)<=0):raise ValueError('Non-monotonic registration anchors')
        yy,xx=np.mgrid[:h,:w].astype('float32');my=np.interp(yy,dst,src).astype('float32')
        # Preserve the head as a rigid image region; blend the small horizontal
        # registration offset smoothly toward the independently located pelvis.
        u=np.clip((yy-(fy+34))/(hy-(fy+34)),0,1);u=u*u*(3-2*u)
        shift=(fx-face[0]*s)*(1-u)+(hx-hip[0]*s)*u;mx=(xx-shift)/s
        rgba=im.astype('float32')/255;rgba[:,:,3]=alpha;rgba[:,:,:3]*=alpha[:,:,None]
        rgba=cv2.remap(rgba,mx.astype('float32'),my,cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT);rgba=np.clip(rgba,0,1);rgba[:,:,:3]/=np.maximum(rgba[:,:,3:4],1e-8)
        images[k['id']]=rgba
        transformedFace=None if 'face' in k else face_center(np.uint8(np.clip(rgba*255,0,255)),[0,0,w,int(hy-35)])
        report.append({'id':k['id'],'face':face.tolist(),'hip':hip.tolist(),'soleY':sole,'ySource':src.tolist(),'yTarget':dst.tolist(),'xScale':s,'faceAfter':None if transformedFace is None else transformedFace.tolist(),'faceResidual':None if transformedFace is None else float(np.linalg.norm(transformedFace-[fx,fy])),'removedLowAlphaPixels':int(np.sum((im[:,:,3]>0)&(alpha==0)))})
    # Optional same-view, same-expression region lock. This is compositing an
    # accepted drawing, not invented detail or a head-turn animation solution.
    lock=c.get('stableTop')
    if lock:
        reference=images[lock['reference']].copy();weight=np.clip((lock['endY']-np.arange(h))/(lock['endY']-lock['startY']),0,1)[:,None,None]
        reference[:,:,:3]*=reference[:,:,3:4]
        for key,rgba in images.items():
            rgba[:,:,:3]*=rgba[:,:,3:4];rgba=rgba*(1-weight)+reference*weight
            rgba[:,:,:3]/=np.maximum(rgba[:,:,3:4],1e-8);images[key]=rgba
    for key,rgba in images.items():Image.fromarray(np.uint8(np.clip(rgba*255,0,255))).save(out/(key+'.png'))
    (out/'registration.json').write_text(json.dumps({'config':c,'records':report,'measurementStage':'After registration, before optional stableTop compositing','scope':'Complete-cel alignment. No proof of limb identity or natural walking.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cels':len(report),'maxFaceResidual':max((r['faceResidual'] for r in report if r['faceResidual'] is not None),default=None),'stableTop':lock}))

if __name__=='__main__':main()
