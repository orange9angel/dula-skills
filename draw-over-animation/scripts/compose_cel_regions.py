"""Lock reviewed donor regions into artwork; never infer story state from pixels."""
import argparse,json,hashlib
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--episode',type=Path,required=True);ap.add_argument('--config',required=True);a=ap.parse_args()
    cfg=json.loads((a.episode/a.config).read_text(encoding='utf-8'));reports=[]
    for item in cfg['items']:
        base=np.array(Image.open(a.episode/item['base']).convert('RGBA'));donor=np.array(Image.open(a.episode/item['donor']).convert('RGBA'))
        if base.shape!=donor.shape:raise ValueError('Donor size mismatch')
        h,w=base.shape[:2];mask=np.zeros((h,w),np.uint8)
        for poly in item.get('polygons',[]):cv2.fillPoly(mask,[np.array(poly,np.int32)],255)
        for x,y,rw,rh in item.get('rects',[]):cv2.rectangle(mask,(x,y),(x+rw-1,y+rh-1),255,-1)
        weight=np.clip(cv2.distanceTransform(mask,cv2.DIST_L2,3)/item.get('feather',4),0,1)
        out=np.uint8(np.clip(base*(1-weight[:,:,None])+donor*weight[:,:,None],0,255))
        if item.get('preserveAlpha',True):out[:,:,3]=base[:,:,3]
        assert np.array_equal(out[mask==0],base[mask==0])
        p=a.episode/item['output'];p.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(out).save(p)
        reports.append({'output':item['output'],'outsideRegionDifference':0,'alphaDifference':int(np.max(np.abs(out[:,:,3].astype(int)-base[:,:,3].astype(int)))),'preserveAlpha':item.get('preserveAlpha',True),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    (a.episode/cfg['report']).write_text(json.dumps(reports,indent=2),encoding='utf-8');print(json.dumps(reports))

if __name__=='__main__':main()
