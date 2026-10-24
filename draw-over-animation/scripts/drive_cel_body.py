"""Bounded same-view cel body repair with pose-derived shared torso motion.

Reuses one clean torso drawing, preserves authored limb cels with explicit masks,
and drives the assembled body from the measured 3D hip/shoulder motion. It does
not synthesize inbetweens or prove natural walking. Masks are shot-specific.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt
from stabilize_cel_anchors import face_center


def premultiply(image):
    rgba = np.asarray(image).astype('float32') / 255
    rgba[:, :, :3] *= rgba[:, :, 3:4]
    return rgba


def over(front, back):
    return front + back * (1 - front[:, :, 3:4])


def save_rgba(path, rgba):
    result = rgba.copy()
    result[:, :, :3] /= np.maximum(result[:, :, 3:4], 1e-8)
    Image.fromarray(np.uint8(np.clip(result * 255, 0, 255))).save(path)


def polygon_mask(size, polygons):
    image = Image.new('L', tuple(size))
    draw = ImageDraw.Draw(image)
    for polygon in polygons:
        if polygon:
            draw.polygon([tuple(p) for p in polygon], fill=255)
    return np.array(image).astype('float32') / 255


def fit_periodic(values, harmonics):
    phase = np.arange(len(values)) / len(values) * 2 * np.pi
    basis = np.array([np.ones(len(phase))] + [f(k * phase) for k in range(1, harmonics + 1) for f in [np.cos, np.sin]]).T
    return basis @ np.linalg.lstsq(basis, np.asarray(values), rcond=None)[0]


def project_motion(capture, camera):
    pos = np.array(camera['position'], float)
    forward = np.array(camera['lookAt'], float) - pos
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    width, height = camera['size']
    focal = height / (2 * np.tan(np.deg2rad(camera['fov'] / 2)))
    tracks, errors = [], []
    for row in capture['rows']:
        pose = row['state']['motion']['pose']
        yaw = pose['yaw']; co, si = np.cos(yaw), np.sin(yaw)
        def project(point):
            x, y, z = [point[k] for k in ['x', 'y', 'z']]
            v = np.array([co*x + si*z, y, -si*x + co*z]) - pos
            return np.array([width/2 + focal*np.dot(v, right)/np.dot(v, forward), height/2 - focal*np.dot(v, up)/np.dot(v, forward)])
        hips = [project(pose[s+'Leg'][0]) for s in ['left', 'right']]
        shoulders = [project(pose[s+'Arm'][0]) for s in ['left', 'right']]
        tracks.append([*np.mean(hips, axis=0), *np.mean(shoulders, axis=0), row['state']['motion']['torso']['yaw']])
        for side in ['left', 'right']:
            if 'joints' in row['state']:
                errors.extend(np.linalg.norm(np.array([project(p) for p in pose[side+'Leg']]) - row['state']['joints'][side], axis=1))
    if errors and max(errors) > .01:
        raise ValueError('Camera projection does not reproduce captured joints')
    return np.asarray(tracks), float(max(errors, default=0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episode', required=True, type=Path)
    parser.add_argument('--config', required=True)
    args = parser.parse_args(); root = args.episode
    cfg = json.loads((root/args.config).read_text(encoding='utf-8'))
    out = root/cfg['output']; out.mkdir(parents=True, exist_ok=True)
    for sub in ['layers', 'assembled', 'frames', 'revised']:
        (out/sub).mkdir(exist_ok=True)
    width, height = cfg['size']; yy, xx = np.mgrid[:height, :width].astype('float32')
    # Normalize the single clean plate once. Its drawing remains stable in body
    # coordinates; the pose motion below moves its head, neck and torso together.
    plate_cfg = cfg['plate']
    plate = np.array(Image.open(root/plate_cfg['file']).convert('RGBA').resize((width, height), Image.Resampling.LANCZOS))
    alpha = plate[:, :, 3].astype('float32')/255
    alpha[distance_transform_edt(alpha < plate_cfg.get('coreAlpha', .86)) > 1.5] = 0
    face = face_center(plate, cfg['faceROI'])
    source_y = [0, face[1], plate_cfg['waist'][1], plate_cfg['hemY'], height]
    target_y = [cfg['faceTarget'][1]-face[1], cfg['faceTarget'][1], cfg['waistTarget'][1], plate_cfg['targetHemY'], height+plate_cfg['targetHemY']-plate_cfg['hemY']]
    map_y = np.interp(yy, target_y, source_y).astype('float32')
    plate[:, :, 3] = np.uint8(alpha*255)
    lower_shift = np.clip((yy-plate_cfg.get('waistShiftStartY',255))/(cfg['waistTarget'][1]-plate_cfg.get('waistShiftStartY',255)),0,1)
    lower_shift = lower_shift*lower_shift*(3-2*lower_shift)*plate_cfg.get('waistShiftX',0)
    map_x = (xx-cfg['waistTarget'][0]-lower_shift)/plate_cfg.get('xScale',1)+plate_cfg['waist'][0]
    torso = cv2.remap(premultiply(plate), map_x.astype('float32'), map_y, cv2.INTER_CUBIC)
    torso = np.clip(torso, 0, 1)
    head = premultiply(Image.open(root/plate_cfg['headReference']).convert('RGBA'))
    weight = np.clip((plate_cfg['headEnd']-yy)/(plate_cfg['headEnd']-plate_cfg['headStart']), 0, 1)[:, :, None]
    torso = head*weight + torso*(1-weight)
    save_rgba(out/'layers/full_body.png', torso)
    # Keep the authored pelvis and its leg connections. The clean chest ends
    # across the waist overlap, not across the thigh silhouettes.
    torso *= np.clip((cfg['torsoEndY']-yy)/(cfg['torsoEndY']-cfg['torsoFadeY']), 0, 1)[:, :, None]
    save_rgba(out/'layers/torso.png', torso)
    prepared, original = {}, {}
    for cel in cfg['cels']:
        key = cel['id']
        original[key] = premultiply(Image.open(root/cel['file']).convert('RGBA'))
        near_mask = polygon_mask(cfg['size'], [cel['near'][0]]+cel.get('attachments',[]))
        weapon_mask=polygon_mask(cfg['size'],cel['weapon'])
        color=original[key][:,:,:3]/np.maximum(original[key][:,:,3:4],1e-8)
        # The declared purple-metal palette excludes trouser pixels inside a
        # hooked blade's polygon. This is not a general semantic segmentation.
        weapon_mask*=((color[:,:,2]-color[:,:,0])>cfg.get('weaponBlueDelta',.025))
        near_mask=np.maximum(near_mask,weapon_mask)
        far_mask = polygon_mask(cfg['size'], cel.get('far', []))
        lower_mask = (yy >= cfg['lowerCut']).astype('float32')
        # Draw the original legs and authored far arm behind the clean torso;
        # the near arm and prop retain their original foreground occlusion.
        back = original[key]*lower_mask[:, :, None]*(1-near_mask[:,:,None])*(1-far_mask[:,:,None])
        far = original[key]*far_mask[:,:,None]
        front = original[key]*near_mask[:, :, None]
        delta = np.array(cfg['shoulderTarget'])-np.array(cel['shoulder'])
        arm_follow = np.clip((cfg['armAnchorEndY']-yy)/(cfg['armAnchorEndY']-cfg['armAnchorStartY']), 0, 1)
        front = cv2.remap(front, xx-arm_follow.astype('float32')*delta[0], yy-arm_follow.astype('float32')*delta[1], cv2.INTER_CUBIC)
        # Register the authored waist to the clean chest before blending color.
        # Landmarks describe the body, not a row union that includes a weapon or
        # crossing arm. The authored lower legs stay outside this registration.
        waist_map = xx.copy()
        profile=np.array(cel['waistProfile'],float)
        last_target=None
        for y in range(cfg['lowerCut'], cfg['waistWarpEndY']):
            source_x = np.flatnonzero(torso[y,:,3] > .05)
            lo,hi = np.interp(y,profile[:,0],profile[:,1]),np.interp(y,profile[:,0],profile[:,2])
            if len(source_x)>1:last_target=(float(source_x[0]),float(source_x[-1]))
            if last_target is None:continue
            target_lo,target_hi=last_target
            u=np.clip((y-cfg['torsoFadeY'])/(cfg['waistWarpEndY']-cfg['torsoFadeY']),0,1);u=u*u*(3-2*u)
            left,right=target_lo+(lo-target_lo)*u,target_hi+(hi-target_hi)*u
            inside=(xx[y]>=min(lo,left)-6)&(xx[y]<=max(hi,right)+6)
            waist_map[y,inside]=((xx[y]-left)/(right-left)*(hi-lo)+lo)[inside]
        back=cv2.remap(back,waist_map,yy,cv2.INTER_CUBIC)
        support_alpha=cv2.remap(original[key][:,:,3],waist_map,yy,cv2.INTER_CUBIC)
        fitted_torso=torso.copy()
        fitted_torso[cfg['torsoFadeY']:]*=support_alpha[cfg['torsoFadeY']:, :, None]
        prepared[key] = np.clip(over(front, over(fitted_torso, over(back,far))), 0, 1)
        # Authored overlap pixels repair narrow uncovered seams at a declared
        # waist/hand join. This cannot fill genuinely unseen character surfaces.
        x0,y0,x1,y1=cel.get('joinUnderlay',cfg['joinUnderlay'])
        support=distance_transform_edt(prepared[key][:,:,3]<.95)<=cfg['joinReach']
        patch=np.zeros((height,width),dtype='float32');patch[y0:y1,x0:x1]=1
        patch*=support
        prepared[key]=over(prepared[key],original[key]*patch[:,:,None])
        save_rgba(out/'assembled'/(key+'.png'), prepared[key])
        save_rgba(out/'layers'/(key+'_near.png'), front)
        save_rgba(out/'layers'/(key+'_far.png'), far)
    capture = json.loads((root/cfg['capture']).read_text(encoding='utf-8'))
    raw, projection_error = project_motion(capture, cfg['camera'])
    smooth = fit_periodic(raw, cfg.get('harmonics', 2)); center = smooth.mean(axis=0)
    exposure = json.loads((root/cfg['exposure']).read_text(encoding='utf-8'))['exposure']
    if len(exposure) != len(smooth):
        raise ValueError('Pose and exposure frame counts must agree')
    weight = np.clip((cfg['footLockY']-yy)/(cfg['footLockY']-cfg['bodyFollowY']), 0, 1)
    weight = weight*weight*(3-2*weight)
    pivot = np.array(cfg['pivot'], float)
    background = np.array(cfg.get('background', [128,136,144]), dtype='float32')/255
    font = ImageFont.truetype(cfg['font'], 22); small = ImageFont.truetype(cfg['font'], 16)
    records = []
    for row, pose in zip(exposure, smooth):
        key = cfg.get('aliases', {}).get(row['key'], row['key'])
        dy = (pose[1]-center[1])*cfg.get('bobGain', 1)
        tilt = ((pose[2]-pose[0])-(center[2]-center[0]))/(center[1]-center[3])
        perspective = (pose[4]-center[4])*cfg.get('twistGain', .12)
        dx_field = (tilt*(pivot[1]-yy)+perspective*(xx-pivot[0]))*weight
        dy_field = dy*weight
        # Feet stay in the authored cel. This is a bounded registration field,
        # not a contact solver or a replacement for a missing walking pose.
        rgba = np.clip(cv2.remap(prepared[key], xx-dx_field.astype('float32'), yy-dy_field.astype('float32'), cv2.INTER_CUBIC), 0, 1)
        rgb = np.uint8(np.clip((rgba[:, :, :3]+background*(1-rgba[:, :, 3:4]))*255, 0, 255))
        if cfg.get('beforeFrames'):
            before_rgb = np.array(Image.open(root/cfg['beforeFrames']/f"{row['i']:04d}.png").convert('RGB'))
            if before_rgb.shape != (height, width, 3):
                raise ValueError('Comparison baseline dimensions do not match')
        else:
            before = original[key]; before_rgb = np.uint8(np.clip((before[:, :, :3]+background*(1-before[:, :, 3:4]))*255, 0, 255))
        image = Image.new('RGB', (width*2, height+74), '#18212f')
        image.paste(Image.fromarray(before_rgb), (0,44)); image.paste(Image.fromarray(rgb), (width,44))
        draw = ImageDraw.Draw(image)
        for i, label in enumerate(cfg['labels']):draw.text((i*width+12,10), label, font=font, fill='white')
        draw.text((12,height+49), f"{row['t']:.3f}s / {key} / "+cfg['footer'], font=small, fill='#ffcf8a')
        name = f"{row['i']:04d}.png"
        image.save(out/'frames'/name, compress_level=2); Image.fromarray(rgb).save(out/'revised'/name, compress_level=2)
        points = {name:[float(p[0]+tilt*(pivot[1]-p[1])+perspective*(p[0]-pivot[0])),float(p[1]+dy)] for name,p in cfg['reviewPoints'].items()}
        records.append({'i':row['i'], 't':row['t'], 'key':key, 'dy':float(dy), 'tilt':float(tilt), 'perspective':float(perspective), 'points':points})
    (out/'report.json').write_text(json.dumps({'config':cfg, 'projectionMaxError':projection_error, 'motion':records,
        'scope':'Body-coordinate art reuse plus measured hip/shoulder motion. No natural-motion or world-contact pass.'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'frames':len(records), 'projectionMaxError':projection_error, 'bodyYRange':np.ptp([r['dy'] for r in records])}))


if __name__ == '__main__':
    main()
