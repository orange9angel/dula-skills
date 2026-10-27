"""Slice recorded/generated footfalls and place them at final animation contacts.

No audio synthesis. Config supplies source material, exact contact timeline and
shot perspective. Output retains provider provenance and source fingerprints.
"""
from pathlib import Path
import argparse,hashlib,json
import librosa
import numpy as np
import soundfile as sf

def step_slices(path,sr):
    y,_=librosa.load(path,sr=sr,mono=True)
    on=librosa.onset.onset_detect(y=y,sr=sr,hop_length=240,units='time',backtrack=True)
    if not len(on):raise ValueError(f'No footfall onsets: {path}')
    groups=[]
    for t in on:
        if groups and t-groups[-1][-1]<.30:groups[-1].append(t)
        else:groups.append([t])
    out=[]
    for i,g in enumerate(groups):
        begin=max(0,g[0]-.015);end=min(g[0]+.38,groups[i+1][0]-.02 if i+1<len(groups) else len(y)/sr)
        s=y[round(begin*sr):round(end*sr)].copy()
        if len(s)<sr*.06 or np.max(np.abs(s))<.001:continue
        s/=np.max(np.abs(s));fade=min(int(.03*sr),len(s)//4);s[-fade:]*=np.linspace(1,0,fade)
        out.append(s)
    if not out:raise ValueError(f'No usable footfalls: {path}')
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('episode',type=Path);p.add_argument('--config',required=True);a=p.parse_args();root=a.episode.resolve()
    cfg=json.loads((root/a.config).read_text(encoding='utf-8'));contacts=json.loads((root/cfg['contacts']).read_text(encoding='utf-8'));sr=48000
    out=np.zeros((round(cfg['duration']*sr),2),np.float32);rng=np.random.default_rng(20261027);sources={};events=[];cache={}
    for row in contacts['contacts']:
        spec=cfg['shots'].get(row['shot'])
        if not spec:continue
        path=root/spec['source']
        if path not in cache:
            cache[path]=step_slices(path,sr);sources[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
        steps=cache[path];s=steps[(row['step']-1)%len(steps)]
        # Child receding into depth: perspective changes actual gain and pan.
        height=row['plate'][2];gain=spec.get('gain',.08)*min(1.2,max(.18,height/spec.get('referenceHeight',250)))*rng.uniform(.88,1)
        pan=max(-.5,min(.5,(row['plate'][0]-960)/960));lr=np.sqrt([(1-pan)/2,(1+pan)/2])
        at=round(row['time']*sr);m=min(len(s),len(out)-at);out[at:at+m]+=s[:m,None]*lr*gain
        events.append(dict(row,gain=float(gain),sample=int((row['step']-1)%len(steps))))
    target=root/cfg['output'];target.parent.mkdir(parents=True,exist_ok=True);sf.write(target,out,sr,subtype='PCM_24')
    report={'provider':'derived from Volcano Seed-Audio','sources':sources,'contacts_sha256':hashlib.sha256((root/cfg['contacts']).read_bytes()).hexdigest(),'events':events,'peak':float(np.max(np.abs(out)))}
    target.with_suffix('.source.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(f'{len(events)} contacts, peak {report["peak"]:.3f} -> {target}')
if __name__=='__main__':main()
