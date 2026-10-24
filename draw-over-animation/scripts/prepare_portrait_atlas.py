"""Register atlas mouth donors and lock their influence to explicit face windows.

The atlas is artwork; this tool does not generate facial anatomy. Review every
crop and donor before accepting. All pixels outside each mouth window stay exact.
"""
import argparse,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--episode',type=Path,required=True);ap.add_argument('--config',required=True);a=ap.parse_args()
    cfg=json.loads((a.episode/a.config).read_text(encoding='utf-8'));atlas=Image.open(a.episode/cfg['atlas']).convert('RGBA');out=a.episode/cfg['output'];out.mkdir(parents=True,exist_ok=True);reports=[]
    for actor,spec in cfg['actors'].items():
        base=np.array(atlas.crop(spec['closedRect']));donor=np.array(atlas.crop(spec['openRect']));h,w=base.shape[:2]
        if donor.shape!=base.shape:raise ValueError('Atlas cell dimensions differ')
        # Explicit color/border exclusions remove a neighboring atlas cell only.
        # Never infer foreground removal from color over the entire portrait.
        for im in [base,donor]:
            for rule in spec.get('neighborExclusions',[]):
                x,y,rw,rh=rule['rect'];region=im[y:y+rh,x:x+rw];rgb=region[:,:,:3].astype(float)
                remove=(rgb[:,:,0]>rgb[:,:,2]*1.25)&(rgb[:,:,0]>80) if rule['color']=='warm' else (rgb[:,:,2]>rgb[:,:,0]*1.18)&(rgb[:,:,2]>45)
                region[remove]=0
        mask=np.zeros((h,w),np.uint8);x,y,rw,rh=spec['alignmentROI'];mask[y:y+rh,x:x+rw]=255
        warp=np.eye(2,3,dtype=np.float32)
        score,warp=cv2.findTransformECC(cv2.cvtColor(base[:,:,:3],cv2.COLOR_RGB2GRAY),cv2.cvtColor(donor[:,:,:3],cv2.COLOR_RGB2GRAY),warp,cv2.MOTION_EUCLIDEAN,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,120,1e-6),mask,5)
        angle=float(np.rad2deg(np.arctan2(warp[1,0],warp[0,0])))
        if abs(angle)>3 or np.linalg.norm(warp[:,2])>24:raise ValueError('Donor registration exceeds local-edit limits')
        aligned=cv2.warpAffine(donor,warp,(w,h),flags=cv2.INTER_CUBIC|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REPLICATE)
        x,y,rw,rh=spec['mouthWindow'];yy,xx=np.mgrid[:h,:w].astype('float32');edge=np.minimum.reduce([xx-x,x+rw-1-xx,yy-y,y+rh-1-yy]);blend=np.clip(edge/spec.get('feather',5),0,1);blend=blend*blend*(3-2*blend)
        opened=np.uint8(np.clip(base*(1-blend[:,:,None])+aligned*blend[:,:,None],0,255))
        pivot=spec['upperLipY'];map_y=yy+(pivot+(yy-pivot)/.58-yy)*blend
        half_donor=cv2.remap(opened,xx,map_y,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
        half=np.uint8(np.clip(base*(1-blend[:,:,None])+half_donor*blend[:,:,None],0,255))
        outside=blend==0
        for name,im in [('closed',base),('half',half),('open',opened)]:
            assert np.array_equal(im[outside],base[outside]);Image.fromarray(im).save(out/f'{actor}_{name}.png')
        blink_report=None
        if cfg.get('blinkAtlas'):
            blink=np.array(Image.open(a.episode/cfg['blinkAtlas']).convert('RGBA').crop(spec['closedRect']))
            stable=(base[:,:,3]>250).astype('uint8')*255
            for x,y,rw,rh in spec['eyeWindows']+[spec['mouthWindow']]:stable[y:y+rh,x:x+rw]=0
            bw=np.eye(2,3,dtype=np.float32)
            bs,bw=cv2.findTransformECC(cv2.cvtColor(base[:,:,:3],cv2.COLOR_RGB2GRAY),cv2.cvtColor(blink[:,:,:3],cv2.COLOR_RGB2GRAY),bw,cv2.MOTION_EUCLIDEAN,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,100,1e-6),stable,5)
            if np.linalg.norm(bw[:,2])>12:raise ValueError('Blink donor registration exceeds local-edit limits')
            blink=cv2.warpAffine(blink,bw,(w,h),flags=cv2.INTER_CUBIC|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REPLICATE)
            eye_blend=np.zeros((h,w),dtype='float32')
            for x,y,rw,rh in spec['eyeWindows']:
                edge=np.minimum.reduce([xx-x,x+rw-1-xx,yy-y,y+rh-1-yy]);weight=np.clip(edge/4,0,1);eye_blend=np.maximum(eye_blend,weight*weight*(3-2*weight))
            overlay=blink.copy();overlay[:,:,3]=np.uint8(eye_blend*base[:,:,3]);Image.fromarray(overlay).save(out/f'{actor}_blink_overlay.png')
            composed=np.uint8(base*(1-eye_blend[:,:,None])+blink*eye_blend[:,:,None]);assert np.array_equal(composed[eye_blend==0],base[eye_blend==0]);Image.fromarray(composed).save(out/f'{actor}_blink_preview.png')
            blink_report={'registrationScore':bs,'warp':bw.tolist(),'eyeWindows':spec['eyeWindows'],'outsideWindowMaxDifference':0}
        reports.append({'actor':actor,'size':[w,h],'registrationScore':score,'warp':warp.tolist(),'mouthWindow':spec['mouthWindow'],'outsideWindowMaxDifference':0,'blink':blink_report})
    (out/'registration.json').write_text(json.dumps({'config':cfg,'actors':reports},indent=2),encoding='utf-8');print(json.dumps(reports))


if __name__=='__main__':main()
