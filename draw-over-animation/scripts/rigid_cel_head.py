"""Bounded, single-view head projection driven by independent source rotations.

Depth is authored for this view, not inferred anatomy or a complete head mesh.
All head points share one rigid 3D transform; a separate neck underlap joins the
unchanged body. Large turns / newly visible surfaces require additional art.
"""
import json
import cv2
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.ndimage import distance_transform_edt
from scipy.spatial.transform import Rotation, Slerp
from drive_cel_body import fit_periodic, polygon_mask


def head_track(root, cfg, capture, camera):
    data=json.loads((root/cfg['motionFile']).read_text(encoding='utf-8'))
    matrices=np.asarray([r[cfg.get('bone','head')] for r in data['orientations']])
    times=np.asarray([r['state']['motion']['sourceFrame'] for r in capture['rows']])
    rotations=Slerp(np.arange(len(matrices)),Rotation.from_matrix(matrices))(times)
    delta=(rotations*rotations.mean().inv()).as_rotvec()
    # Periodic fit preserves the source phase relation; no second arbitrary sine.
    delta=fit_periodic(delta,cfg.get('harmonics',2));delta-=delta.mean(axis=0)
    delta*=np.asarray(cfg.get('rotationGain',[1,1,1]))
    forward=np.asarray(camera['lookAt'])-np.asarray(camera['position']);forward=forward/np.linalg.norm(forward)
    right=np.cross(forward,[0,1,0]);right=right/np.linalg.norm(right);up=np.cross(right,forward)
    view=np.stack([right,-up,-forward]) # image X right, Y down, Z towards viewer
    mirror=np.diag(cfg['sourceAxes'])
    if mirror.shape!=(3,3) or not np.allclose(mirror@mirror.T,np.eye(3)):
        raise ValueError('sourceAxes must contain three axis signs, each +1 or -1')
    result=[]
    for row,rv in zip(capture['rows'],delta):
        yaw=row['state']['motion']['pose']['yaw'];c,s=np.cos(yaw),np.sin(yaw)
        heading=np.array([[c,0,s],[0,1,0],[-s,0,c]])
        basis=view@heading@mirror
        result.append(basis@Rotation.from_rotvec(rv).as_matrix()@basis.T)
    result=np.asarray(result)
    degrees=Rotation.from_matrix(result).as_rotvec()*180/np.pi
    return result,{'sourceFrameRange':[float(times.min()),float(times.max())],
                   'cameraRotationRangeDegrees':np.ptp(degrees,axis=0).tolist(),
                   'sourceRotationRangeDegrees':np.ptp(np.rad2deg(delta),axis=0).tolist(),
                   'rotationOrthogonalityError':float(np.max(abs(result@result.transpose(0,2,1)-np.eye(3)))),
                   'rotationDeterminantRange':[float(np.linalg.det(result).min()),float(np.linalg.det(result).max())]}


class RigidCelHead:
    def __init__(self,body,cfg,grid):
        self.cfg=cfg;self.yy,self.xx=grid;h,w=self.xx.shape
        if cfg['focalPx']<=max(abs(x) for x in cfg['depthRange'])*2:
            raise ValueError('Depth is too large for the declared projection focal length')
        self.mask=polygon_mask([w,h],cfg['maskPolygons'])
        self.body=body*(1-self.mask[:,:,None])
        self.head=body*self.mask[:,:,None]
        # Extend only the hidden neck cut beneath existing opaque collar pixels.
        # Do not expand the hair/face exterior or paint a halo around the head.
        supported=(self.mask>.5)&(body[:,:,3]>.8)
        if not supported.any():raise ValueError('Head mask has no opaque source pixels')
        distance,nearest=distance_transform_edt(~supported,return_indices=True)
        extension=(self.mask<.5)&(body[:,:,3]>.8)&(distance<=cfg.get('underlapPx',3))
        self.head[extension]=body[nearest[0][extension],nearest[1][extension]]
        points=np.asarray(cfg['depthLandmarks'],float)
        surface=RBFInterpolator(points[:,:2],points[:,2],kernel='thin_plate_spline',smoothing=cfg.get('depthSmoothing',2))
        # Evaluate a small uniform grid, then interpolate the smooth depth field.
        sy,sx=np.mgrid[0:h:4,0:w:4].astype(float)
        depth=surface(np.column_stack([sx.ravel(),sy.ravel()])).reshape(sx.shape)
        # remap the coarse grid at its actual coordinates (resize shifts samples).
        self.depth=cv2.remap(depth.astype('float32'),self.xx/4,self.yy/4,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
        self.depth=np.clip(self.depth,*cfg['depthRange'])
        self.last_report={}

    def project(self,x,y,matrix,translation):
        cfg=self.cfg;cx,cy=cfg['pivot'];f=cfg['focalPx']
        z=cv2.remap(self.depth,np.asarray(x,dtype='float32'),np.asarray(y,dtype='float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        # Inverse perspective ensures the authored view is exact at zero pose.
        X=(x-cx)*(1-z/f);Y=(y-cy)*(1-z/f)
        p=np.stack([X,Y,z-cfg.get('pivotDepth',0)],axis=-1)@matrix.T
        p[:,:,2]+=cfg.get('pivotDepth',0)
        scale=f/(f-p[:,:,2])
        return p[:,:,0]*scale+cx+translation[0],p[:,:,1]*scale+cy+translation[1]

    def render(self,matrix,translation):
        xx,yy=self.xx,self.yy
        angle=float(np.rad2deg(Rotation.from_matrix(matrix).magnitude()))
        if angle>self.cfg.get('maxRotationDegrees',8):
            raise ValueError('Head angle exceeds the declared view limit; supply additional art')
        px,py=self.project(xx,yy,matrix,translation)
        field=np.stack([px-xx,py-yy],axis=-1).astype('float32')
        sx,sy=xx.copy(),yy.copy()
        for _ in range(10):
            d=cv2.remap(field,sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            sx,sy=xx-d[:,:,0],yy-d[:,:,1]
        result=np.clip(cv2.remap(self.head,sx,sy,cv2.INTER_CUBIC),0,1)
        qx,qy=self.project(sx,sy,matrix,translation)
        active=result[:,:,3]>.5
        residual=float(np.max(np.hypot(qx-xx,qy-yy)[active]))
        jxx=np.gradient(px,axis=1);jxy=np.gradient(px,axis=0)
        jyx=np.gradient(py,axis=1);jyy=np.gradient(py,axis=0)
        jacobian=jxx*jyy-jxy*jyx
        support=self.head[:,:,3]>.5
        self.last_report={'inverseResidualMaxPx':residual,'jacobianRange':[float(jacobian[support].min()),float(jacobian[support].max())],
                          'translationPx':[float(x) for x in translation],
                          'rotationVectorDegrees':Rotation.from_matrix(matrix).as_rotvec().tolist()}
        self.last_report['rotationVectorDegrees']=np.rad2deg(self.last_report['rotationVectorDegrees']).tolist()
        if self.last_report['jacobianRange'][0]<=0:
            raise ValueError('Head projection folds; reduce the view range or supply another drawing')
        return result
