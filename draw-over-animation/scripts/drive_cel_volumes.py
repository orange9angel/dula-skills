"""Same-view chest/pelvis depth warp with source hip rotation and stable armor.

This is a bounded curved-surface projection, not a reconstructed 3D character.
Leg drawings retain their authored poses. Exposure/contact failures remain
independent review items. Uses declared layer masks and a calibrated palette.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from drive_cel_body import premultiply, over, save_rgba, polygon_mask, fit_periodic, project_motion


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x*x*(3-2*x)


def volume_points(x, y, motion, cfg, part):
    """Forward project a shallow convex surface; pixel XY, camera-facing Z."""
    profile = np.asarray(cfg['depthProfile'], float)
    center = np.interp(y, profile[:, 0], profile[:, 1])
    radius = np.interp(y, profile[:, 0], profile[:, 2])
    depth = np.interp(y, profile[:, 0], profile[:, 3])
    z = depth*np.maximum(0, 1-((x-center)/radius)**2)
    blend = smoothstep((y-cfg['chestY'])/(cfg['pelvisY']-cfg['chestY']))
    if part == 'arms':
        blend = np.zeros_like(blend)
        z = z + cfg.get('armDepthOffset', 5)
    elif part == 'legs':
        blend = np.ones_like(blend)
    yaw = motion['chestYaw']*(1-blend)+motion['hipYaw']*blend
    roll = motion['chestRoll']*(1-blend)+motion['hipRoll']*blend
    weight = 1-smoothstep((y-cfg['followEndY'])/(cfg['footLockY']-cfg['followEndY']))
    # Rotation changes apparent cross-section and moves painted details across
    # the curved surface. Mean depth subtraction avoids unrelated lateral drift.
    px, py = cfg['pivot']
    dx = (x-center)*(np.cos(yaw)-1)+(z-depth*.72)*np.sin(yaw)
    xx = x+dx
    yy = y
    rx = (xx-px)*np.cos(roll)-(yy-py)*np.sin(roll)+px
    ry = (xx-px)*np.sin(roll)+(yy-py)*np.cos(roll)+py
    lean = motion['lean']*(py-y)
    return x+(rx-x+lean+motion['dx'])*weight, y+(ry-y+motion['dy'])*weight


def warp(image, motion, cfg, part, grid, cache):
    if not np.any(image[:, :, 3] > .05):
        return image.copy(), 0.0
    yy, xx = grid
    if part not in cache:
        px,py=volume_points(xx,yy,motion,cfg,part)
        displacement=np.stack([px-xx,py-yy],axis=-1).astype('float32')
        sx,sy=xx.copy(),yy.copy()
        for _ in range(7):
            delta=cv2.remap(displacement,sx,sy,cv2.INTER_LINEAR)
            sx,sy=xx-delta[:,:,0],yy-delta[:,:,1]
        cache[part]=(sx,sy)
    sx,sy=cache[part]
    px, py = volume_points(sx, sy, motion, cfg, part)
    active = image[:, :, 3] > .05
    residual = float(np.max(np.hypot(px-xx, py-yy)[active]))
    return np.clip(cv2.remap(image, sx.astype('float32'), sy.astype('float32'), cv2.INTER_CUBIC),0,1), residual


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--episode',type=Path,required=True);ap.add_argument('--config',required=True)
    ap.add_argument('--frames',type=int,nargs='+',help='Render only these exposure indices for a scoped visual trial')
    args=ap.parse_args();root=args.episode;cfg=json.loads((root/args.config).read_text(encoding='utf-8'))
    base=json.loads((root/cfg['layersConfig']).read_text(encoding='utf-8'))
    out=root/cfg['output'];out.mkdir(parents=True,exist_ok=True)
    for folder in ['frames','revised','layers']:(out/folder).mkdir(exist_ok=True)
    w,h=base['size'];yy,xx=np.mgrid[:h,:w].astype('float32');grid=(yy,xx)
    layerdir=root/base['output']/'layers'
    body=premultiply(Image.open(layerdir/'full_body.png').convert('RGBA'))
    body*=(1-smoothstep((yy-cfg['bodyFadeStartY'])/(cfg['bodyFadeEndY']-cfg['bodyFadeStartY'])))[:,:,None]
    head=None
    if 'head' in cfg:
        from rigid_cel_head import RigidCelHead, head_track
        head=RigidCelHead(body,cfg['head'],grid)
        body=head.body
        save_rgba(out/'layers'/'head.png',head.head)
        save_rgba(out/'layers'/'body_without_head.png',body)
        Image.fromarray(np.uint8((head.depth-cfg['head']['depthRange'][0])/np.ptp(cfg['head']['depthRange'])*255)).save(out/'layers'/'head_depth.png')
    layers={};profile_report=[]
    for cel in base['cels']:
        key=cel['id'];source=premultiply(Image.open(root/cel['file']).convert('RGBA'))
        near=polygon_mask(base['size'],[cel['near'][0]]+cel.get('attachments',[]))
        color=source[:,:,:3]/np.maximum(source[:,:,3:4],1e-8)
        # Preserve the complete shaft/blade, including its dark outline.
        # These explicit contours can include original occluded pixels; they
        # are limited to this small-view motion and require a seam review.
        weapon=polygon_mask(base['size'],cfg.get('weaponOverrides',{}).get(key,cel['weapon']))
        near=np.maximum(near,weapon)
        far=polygon_mask(base['size'],cel.get('far',[]))
        lower=source*(1-near[:,:,None])*(1-far[:,:,None])
        lower*=smoothstep((yy-cfg['legStartY'])/cfg['legBlend'])[:,:,None]
        front=premultiply(Image.open(layerdir/(key+'_near.png')).convert('RGBA'))
        front=over(source*weapon[:,:,None],front)
        # Color filtering can leave dark blade interiors outside the trousers.
        # Keep such detached prop pixels with the foreground, not with thighs.
        count,labels,stats,_=cv2.connectedComponentsWithStats((lower[:,:,3]>.05).astype('uint8'))
        keep=np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=cfg['minLegComponent'])+1
        if not len(keep):raise ValueError('No connected leg layer for '+key)
        leg_support=np.isin(labels,keep)
        detached=lower*(~leg_support)[:,:,None]
        front=over(front,detached)
        lower*=leg_support[:,:,None]
        # Opaque trouser material behind a crossing prop. Its silhouette comes
        # from the observed leg row; its flat color is sampled from that row.
        # No new silhouette, garment detail or disconnected gap is synthesized.
        filled=0
        for y in range(cfg['clothUnderlayY'][0],cfg['clothUnderlayY'][1]):
            xs=np.flatnonzero(leg_support[y])
            if len(xs)<12:continue
            a,b=int(xs[0]),int(xs[-1])
            cloth=(lower[y,:,3]>.8)&(color[y,:,0]<.35)&(np.abs(color[y,:,2]-color[y,:,0])<.055)
            if np.count_nonzero(cloth)<6:continue
            hidden=(weapon[y]>0)&(source[y,:,3]>.5)&(np.arange(w)>=a)&(np.arange(w)<=b)
            fill=np.zeros((w,4),dtype='float32');fill[hidden,:3]=np.median(color[y,cloth],axis=0);fill[hidden,3]=1
            lower[y]+=fill*(1-lower[y,:,3:4]);filled+=int(np.count_nonzero(hidden))
        # Register only the thigh roots beneath the armor; preserve knees and
        # feet. Do not infer width from the union of arms and weapons.
        y0=cfg['rootSampleY'];lo_roi,hi_roi=cfg['rootROI']
        counts=np.sum(lower[y0-2:y0+3,lo_roi:hi_roi,3]>.7,axis=0)
        xs=np.flatnonzero(counts>=3)+lo_roi
        if len(xs)<10:raise ValueError('No thigh-root support for '+key)
        lo,hi=float(xs[0]),float(xs[-1]);target_lo,target_hi=cfg['rootTarget']
        source_width=np.sum(lower[:,:,3]>.5,axis=1)
        strength=1-smoothstep((yy-cfg['rootBlendStartY'])/(cfg['rootBlendEndY']-cfg['rootBlendStartY']))
        if cfg.get('rootProfile') == 'translate':
            # A linear shear adjusts the hip attachment without squeezing the
            # row width or adding curvature to straight authored thigh axes.
            strength=np.clip((cfg['rootBlendEndY']-yy)/(cfg['rootBlendEndY']-cfg['rootBlendStartY']),0,1)
            ideal=xx+(lo+hi-target_lo-target_hi)*.5
        elif cfg.get('rootProfile') == 'per_row':
            row_y=[];row_lo=[];row_hi=[]
            for y in range(cfg['legStartY']+cfg['legBlend'],cfg['rootBlendEndY']+1):
                support=np.flatnonzero(lower[y,:,3]>.7)
                if len(support)>=10:
                    row_y.append(y);row_lo.append(support[0]);row_hi.append(support[-1])
            if not row_y:raise ValueError('No thigh contour for '+key)
            left=np.interp(yy,row_y,row_lo);right=np.interp(yy,row_y,row_hi)
            ideal=(xx-target_lo)/(target_hi-target_lo)*(right-left)+left
        else:
            ideal=(xx-target_lo)/(target_hi-target_lo)*(hi-lo)+lo
        mx=xx+(ideal-xx)*strength
        lower=np.clip(cv2.remap(lower,mx.astype('float32'),yy,cv2.INTER_CUBIC),0,1)
        result_width=np.sum(lower[:,:,3]>.5,axis=1)
        probe=(np.arange(h)>=cfg['rootBlendStartY']+2)&(np.arange(h)<cfg['rootBlendEndY'])&(source_width>10)
        ratios=result_width[probe]/source_width[probe]
        back=premultiply(Image.open(layerdir/(key+'_far.png')).convert('RGBA'))
        fitted_body=body
        if 'bodySupportY' in cfg:
            # The clean plate's trouser hem must not overhang the actual thigh.
            # This range must start below every rigid armor tip in this view.
            start,end=cfg['bodySupportY']
            blend=smoothstep((yy-start)/(end-start))
            fitted_body=body*(1-blend*(1-lower[:,:,3]))[:,:,None]
        layers[key]=(lower,front,back,fitted_body)
        save_rgba(out/'layers'/(key+'_legs.png'),lower)
        profile_report.append({'id':key,'sourceRoot':[lo,hi],'targetRoot':cfg['rootTarget'],'occludedClothPixels':filled,
                               'occupiedRowWidthRatio':{'min':float(ratios.min()),'max':float(ratios.max()),'mean':float(ratios.mean())} if len(ratios) else None})
    capture=json.loads((root/base['capture']).read_text(encoding='utf-8'))
    head_matrices,head_report=head_track(root,cfg['head'],capture,base['camera']) if head else (None,None)
    raw,projection_error=project_motion(capture,base['camera'])
    bodytrack=fit_periodic(raw,cfg['harmonics']);center=bodytrack.mean(axis=0)
    angles=[]
    for row in capture['rows']:
        state=row['state']['motion']
        if not state.get('pelvis',{}).get('enabled'):raise ValueError('Capture lacks source pelvis motion')
        angles.append([state['pelvis']['yaw'],state['pelvis']['roll'],state['torso']['yaw'],state['torso']['roll']])
    angles=fit_periodic(np.unwrap(angles,axis=0),cfg['harmonics']);angles-=angles.mean(axis=0)
    exposure=json.loads((root/base['exposure']).read_text(encoding='utf-8'))['exposure']
    if len(exposure)!=len(bodytrack):raise ValueError('Capture and exposure counts differ')
    font=ImageFont.truetype(base['font'],22);small=ImageFont.truetype(base['font'],16)
    bg=np.asarray(base.get('background',[128,136,144]),dtype='float32')/255
    records=[];residuals=[]
    for row,track,angle in zip(exposure,bodytrack,angles):
        if args.frames is not None and row['i'] not in args.frames:continue
        key=base.get('aliases',{}).get(row['key'],row['key'])
        motion={'dx':float((track[0]-center[0])*cfg['lateralGain']), 'dy':float(track[1]-center[1]),
                'lean':float(((track[2]-track[0])-(center[2]-center[0]))/(center[1]-center[3])),
                'hipYaw':float(angle[0]*cfg['hipYawGain']),'hipRoll':float(angle[1]*cfg['hipRollGain']),
                'chestYaw':float(angle[2]*cfg['chestYawGain']),'chestRoll':float(angle[3]*cfg['chestRollGain'])}
        lower,front,back,cel_body=layers[key]
        warped=[];cache={}
        for im,part in [(lower,'legs'),(back,'arms'),(cel_body,'body'),(front,'arms')]:
            result,residual=warp(im,motion,cfg,part,grid,cache);warped.append(result);residuals.append(residual)
        head_frame=None
        if head:
            ax,ay=cfg['head']['anchor']
            tx,ty=volume_points(np.asarray(ax),np.asarray(ay),motion,cfg,'body')
            head_image=head.render(head_matrices[row['i']],(tx-ax,ty-ay))
            warped[2]=over(warped[2],head_image) # collar stays in front of neck/rear hair
            head_frame=head.last_report
        rgba=over(warped[3],over(warped[2],over(warped[0],warped[1])))
        rgb=np.uint8(np.clip((rgba[:,:,:3]+bg*(1-rgba[:,:,3:4]))*255,0,255))
        name=f"{row['i']:04d}.png";Image.fromarray(rgb).save(out/'revised'/name)
        before=Image.open(root/cfg['beforeFrames']/name).convert('RGB')
        pair=Image.new('RGB',(w*2,h+74),'#18212f');pair.paste(before,(0,44));pair.paste(Image.fromarray(rgb),(w,44));draw=ImageDraw.Draw(pair)
        for j,label in enumerate(cfg['labels']):draw.text((j*w+12,10),label,font=font,fill='white')
        draw.text((12,h+49),f"{row['t']:.3f}s / {key} / "+cfg['footer'],font=small,fill='#ffcf8a')
        pair.save(out/'frames'/name)
        if row['i'] in cfg.get('samples',[]):save_rgba(out/'layers'/('body_'+str(row['i'])+'.png'),warped[2])
        records.append({'i':row['i'],'key':key,**motion,**({'head':head_frame} if head_frame else {})})
    if not records:raise ValueError('No exposure frames selected')
    report={'config':cfg,'selectedFrames':args.frames,'motion':records,'rootRegistration':profile_report,'projectionMaxError':projection_error,
            'inverseResidualMaxPx':max(residuals),'scope':'Bounded chest/pelvis curved-surface motion. Original leg/arm pose changes and world contact remain independent review items.'}
    if head:report['head']=head_report
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'frames':len(records),'inverseResidualMaxPx':max(residuals),'hipYawRangeDegrees':float(np.rad2deg(np.ptp(angles[:,0])))}))


if __name__=='__main__':main()
