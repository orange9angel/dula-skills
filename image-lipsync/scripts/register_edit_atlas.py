"""Register same-image edit cells by one similarity transform per cell.

Emits coordinates only. Registration candidates require native-crop review.
"""
import argparse,hashlib,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image
p=argparse.ArgumentParser(__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--donor',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
c=json.loads(a.config.read_text(encoding='utf-8'));w,h=c['cell'];cols=c['columns'];rows=(len(c['targets'])+cols-1)//cols;atlas=Image.open(a.donor).convert('RGB');sx,sy=atlas.width/(cols*w),atlas.height/(rows*h);result=[]
sift=cv2.SIFT_create(contrastThreshold=.015);matcher=cv2.BFMatcher()
for i,t in enumerate(c['targets']):
 x,y,tw,th=t['crop'];base=Image.open(a.config.parent/t['source']).convert('RGB').crop((x,y,x+w,y+h));cx=i%cols*w;cy=i//cols*h
 donor=atlas.crop((round(cx*sx),round(cy*sy),round((cx+w)*sx),round((cy+h)*sy))).resize((w,h),Image.Resampling.LANCZOS)
 b=cv2.cvtColor(np.array(base.resize((w*2,h*2))),cv2.COLOR_RGB2GRAY);d=cv2.cvtColor(np.array(donor.resize((w*2,h*2))),cv2.COLOR_RGB2GRAY)
 mask=np.zeros_like(b);roi=t.get('registrationROI',[35,65,175,140]);rx,ry,rw,rh=roi;mask[2*ry:2*(ry+rh),2*rx:2*(rx+rw)]=255
 for ex,ey,ew,eh in t.get('registrationExclude',[]):mask[2*ey:2*(ey+eh),2*ex:2*(ex+ew)]=0
 kb,db=sift.detectAndCompute(b,mask);kd,dd=sift.detectAndCompute(d,None);good=[m for m,n in matcher.knnMatch(db,dd,k=2) if m.distance<.73*n.distance]
 if len(good)<6:raise SystemExit(f'Insufficient registration features: {t["id"]}')
 bp=np.float32([kb[m.queryIdx].pt for m in good])/2;dp=np.float32([kd[m.trainIdx].pt for m in good])/2
 M,inliers=cv2.estimateAffinePartial2D(dp,bp,method=cv2.RANSAC,ransacReprojThreshold=2,maxIters=10000,confidence=.999)
 if M is None:raise SystemExit('Registration failed '+t['id'])
 scale=float(np.hypot(M[0,0],M[1,0]));rotation=float(np.degrees(np.arctan2(M[1,0],M[0,0])));count=int(inliers.sum())
 if not .6<scale<1.5 or abs(rotation)>5 or count<6:raise SystemExit(f'Unsafe registration: {t["id"]}, {scale=}, {rotation=}, {count=}')
 B=M.copy();B[:,2]+=np.array([x,y])-M[:,:2]@np.array([cx,cy]);error=float(np.mean(np.linalg.norm((dp@M[:,:2].T+M[:,2])-bp,axis=1)[inliers.ravel()>0]))
 result.append({'id':t['id'],'sourceAffine':B.tolist(),'cropSimilarity':M.tolist(),'scale':scale,'rotation':rotation,'inliers':count,'matches':len(good),'meanInlierError':error})
 print(f'{t["id"]}: scale={scale:.3f}, rotation={rotation:.2f}, inliers={count}/{len(good)}, error={error:.2f}',flush=True)
a.output.write_text(json.dumps({'sourceConfig':str(a.config.name),'donor':a.donor.name,'sha256':hashlib.sha256(a.donor.read_bytes()).hexdigest(),'sourceSize':[cols*w,rows*h],'registrations':result,'status':'similarity candidates, native crop review required'},indent=2),encoding='utf-8')
