"""Build explicit-seed mattes for same-source articulated painting parts.
No RGB redraw or inferred anatomy; seeds/polygons belong to the episode.
"""
import argparse,json,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('episode',type=Path);p.add_argument('--config',required=True);a=p.parse_args();root=a.episode.resolve();cfg=json.loads((root/a.config).read_text(encoding='utf-8'));rgb=np.array(Image.open(root/cfg['source']).convert('RGB'));bgr=rgb[:,:,::-1].copy();H,W=rgb.shape[:2];out=root/cfg['maskDirectory'];out.mkdir(parents=True,exist_ok=True);union=np.zeros((H,W),np.uint8);report=[]
jobs={**cfg['parts'],**cfg.get('eraseParts',{})}
for name,s in jobs.items():
 poly=np.array(s['polygon'],np.int32);region=np.zeros((H,W),np.uint8);cv2.fillPoly(region,[poly],1);mask=np.where(region,cv2.GC_PR_FGD,cv2.GC_BGD).astype(np.uint8)
 for stroke in cfg['maskSeeds'][name]:
  points=np.array(stroke['points'],np.int32);cv2.polylines(mask,[points],False,cv2.GC_FGD,stroke.get('width',5));
  for point in points:cv2.circle(mask,tuple(point),max(1,stroke.get('width',5)//2),cv2.GC_FGD,-1)
 mask[region==0]=cv2.GC_BGD;bg=np.zeros((1,65));fg=np.zeros((1,65));cv2.grabCut(bgr,mask,None,bg,fg,5,cv2.GC_INIT_WITH_MASK);alpha=np.uint8(((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD))*255);alpha=cv2.morphologyEx(alpha,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8));alpha[region==0]=0
 rgba=np.full((H,W,4),255,np.uint8);rgba[:,:,3]=alpha;Image.fromarray(rgba).save(out/(name+'.png'))
 if s.get('clearUnderlay',True) and not s.get('occluder'):union=np.maximum(union,alpha)
 distances=cv2.distanceTransform(alpha,cv2.DIST_L2,cv2.DIST_MASK_PRECISE);probes=[]
 for probe in cfg.get('maskProbes',{}).get(name,[]):
  px,py=probe['point'];radius=float(distances[py,px]);probes.append({**probe,'radius':radius,'passed':radius>=probe['minRadius']})
 report.append({'id':name,'pixels':int(np.count_nonzero(alpha)),'probes':probes})
for polygon in cfg.get('clearPolygons',[]):cv2.fillPoly(union,[np.array(polygon,np.int32)],255)
clear=cv2.dilate(union,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)));rgba=np.full((H,W,4),255,np.uint8);rgba[:,:,3]=clear;Image.fromarray(rgba).save(out/'clear_all.png');(out/'mask_report.json').write_text(json.dumps({'sourceSha256':hashlib.sha256((root/cfg['source']).read_bytes()).hexdigest(),'method':'explicit-seed GrabCut alpha mattes; conservative separate clean-plate masks; native contour review required','parts':report},indent=2),encoding='utf-8');print(json.dumps(report))
if any(not p['passed'] for part in report for p in part['probes']):raise SystemExit('Part matte lost a required interior section')
