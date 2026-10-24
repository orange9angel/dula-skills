"""Bake an ASF/AMC skeleton to world joints for a bounded retargeting study."""
import argparse, json, math, hashlib
from pathlib import Path
import numpy as np

def rotation(angles):
    x,y,z=np.radians(angles)
    cx,sx,cy,sy,cz,sz=math.cos(x),math.sin(x),math.cos(y),math.sin(y),math.cos(z),math.sin(z)
    return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])

def convert(asf,amc,fps,scale):
    bones={}; section=''; bone=None; parents={}
    for line in asf.read_text().splitlines():
        a=line.strip().split()
        if not a or a[0].startswith('#'):continue
        if a[0].startswith(':'):section=a[0];continue
        if section==':bonedata':
            if a[0]=='begin':bone={'dof':[]}
            elif a[0]=='end':bones[bone['name']]=bone
            elif a[0]=='name':bone['name']=a[1]
            elif a[0] in ['direction','axis']:bone[a[0]]=list(map(float,a[1:4]))
            elif a[0]=='length':bone['length']=float(a[1])
            elif a[0]=='dof':bone['dof']=a[1:]
        elif section==':hierarchy' and a[0] not in ['begin','end']:
            for child in a[1:]:parents[child]=a[0]
    frames=[]; current=None
    for line in amc.read_text().splitlines():
        a=line.split()
        if not a or a[0].startswith(('#',':')):continue
        if len(a)==1 and a[0].isdigit():
            if current is not None:frames.append(current)
            current={}
        else:current[a[0]]=list(map(float,a[1:]))
    if current:frames.append(current)
    baked=[]
    for f in frames:
        positions={'root':np.array(f['root'][:3])*scale}; matrices={'root':rotation(f['root'][3:6])}
        def solve(name):
            if name in positions:return
            b=bones[name];parent=parents[name];solve(parent)
            angles=[0,0,0]
            for key,value in zip(b['dof'],f.get(name,[])):angles[['rx','ry','rz'].index(key)]=value
            axis=rotation(b['axis']);m=matrices[parent] @ axis @ rotation(angles) @ axis.T
            matrices[name]=m;positions[name]=positions[parent]+m @ (np.array(b['direction'])*b['length']*scale)
        for name in bones:solve(name)
        baked.append({name:np.round(p,7).tolist() for name,p in positions.items()})
    return {'fps':fps,'frames':baked,'bones':bones,'parents':parents,'source':{str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in [asf,amc]},'scale':scale}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--asf',type=Path,required=True);p.add_argument('--amc',type=Path,required=True);p.add_argument('--fps',type=float,required=True);p.add_argument('--scale',type=float,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=convert(a.asf,a.amc,a.fps,a.scale);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,separators=(',',':')),encoding='utf-8');print(json.dumps({'frames':len(out['frames']),'fps':a.fps,'seconds':len(out['frames'])/a.fps}))
