"""Mix existing audio assets against story-derived cue anchors; never synthesize sound."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfilt
SKILLS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SKILLS/'build-ambience-foley'/'scripts'))
from bed_loop import bounded_bed
from mix_envelopes import smooth_activity

def read(path,sr):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ar',str(sr),'-ac','2','pipe:1'])
    return np.frombuffer(raw,dtype='<f4').reshape(-1,2).copy()
def write(path,a,sr):
    path.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-y','-v','error','-f','f32le','-ar',str(sr),'-ac','2','-i','pipe:0','-c:a','pcm_s24le',str(path)],input=a.astype('<f4').tobytes(),check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bed_stats(a,sr):
    mono=a.mean(axis=1);hop=sr//100;n=len(mono)//hop
    env=np.sqrt(np.mean(mono[:n*hop].reshape(n,hop)**2,axis=1)+1e-16)
    sec=np.sqrt(np.mean(mono[:len(mono)//sr*sr].reshape(-1,sr)**2,axis=1)+1e-16)
    centered=env-env.mean();auto=[]
    for lag in range(50,101):
        x,y=centered[:-lag],centered[lag:]
        auto.append(float(np.dot(x,y)/max(1e-15,np.linalg.norm(x)*np.linalg.norm(y))))
    freq=np.fft.rfftfreq(len(mono),1/sr);power=np.abs(np.fft.rfft(mono))**2
    return {'rmsMaxMean':float(sec.max()/sec.mean()),'periodicCorrelation':max(auto),
            'hissRatio':float(power[(freq>=4000)&(freq<=8000)].sum()/max(1e-16,power.sum()))}

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('episode',type=Path);ap.add_argument('--config',required=True);args=ap.parse_args()
    root=args.episode.resolve();c=json.loads((root/args.config).read_text(encoding='utf-8-sig'))
    tl=json.loads((root/c['timeline']).read_text(encoding='utf-8-sig'))
    if sha(root/'script.story')!=tl['sourceSha256']:raise SystemExit('Stale story timeline')
    cues={s['id']:s['start'] for s in tl['segments']}
    def at(anchor):return cues[anchor['cue']]+anchor.get('offset',0)
    start,end=at(c['range']['start']),at(c['range']['end']);sr=c.get('sampleRate',48000);n=round((end-start)*sr)
    buses={k:np.zeros((n,2),np.float32) for k in ['dialogue','foley','ambience','music']};sources=[]
    for track in c['tracks']:
        path=root/track['source'];a=read(path,sr);record={'id':track['id'],'source':track['source'],'sha256':sha(path),'sourceDuration':len(a)/sr}
        if track.get('kind')=='bed':
            a=sosfilt(butter(3,[60,1500],btype='bandpass',fs=sr,output='sos'),a,axis=0).astype(np.float32)
            # Slow level stabilization of the recorded/generated source, not a synthesized waveform.
            env=np.sqrt(uniform_filter1d((a*a).mean(axis=1),size=round(.4*sr))+1e-12)
            target=np.median(env);a*=np.clip(target/np.maximum(env,1e-8),.3,3)[:,None]
            record['bedQC']=bed_stats(a,sr)
            if record['bedQC']['rmsMaxMean']>=1.4 or record['bedQC']['periodicCorrelation']>=.15 or record['bedQC']['hissRatio']>=.2:
                raise SystemExit('Ambience rejected: '+json.dumps(record['bedQC']))
            a=bounded_bed(a,n,sr,fade_in=.5,fade_out=.5)
            a*=track['rms']/max(1e-8,float(np.sqrt(np.mean(a*a))))
        else:
            offset=round(track.get('sourceOffset',0)*sr);length=round(track.get('length',len(a)/sr)*sr)
            a=a[offset:offset+length]
            if track.get('trimToOnset'):
                energy=np.max(np.abs(a),axis=1);hits=np.flatnonzero(energy>max(.002,float(energy.max())*.12))
                if not len(hits):raise SystemExit('Silent event '+track['id'])
                first=max(0,int(hits[0]) - round(.008*sr));a=a[first:];record['trimmedLead']=first/sr
            a*=track.get('peak',.5)/max(1e-8,float(np.max(np.abs(a))))
            for sec,head in [(track.get('fadeIn',.006),True),(track.get('fadeOut',.03),False)]:
                k=min(len(a)//2,round(sec*sr))
                if k:
                    if head:a[:k]*=np.linspace(0,1,k)[:,None]
                    else:a[-k:]*=np.linspace(1,0,k)[:,None]
        placements=track.get('events',[track.get('start',c['range']['start'])]);record['placements']=[]
        for anchor in placements:
            t=at(anchor);i=round((t-start)*sr);lo=max(0,i);hi=min(n,i+len(a))
            if hi>lo:buses[track['bus']][lo:hi]+=a[lo-i:hi-i]*track.get('gain',1)
            record['placements'].append({'time':t,'duration':len(a)/sr})
        sources.append(record)
    active=np.max(np.abs(buses['dialogue']),axis=1)>.012
    duck=1-.65*smooth_activity(active.astype(np.float32),sr)
    for key in ['music','ambience']:buses[key]*=duck[:,None]
    mix=sum(buses.values());peak=float(np.max(np.abs(mix)));gain=min(1,.74/max(1e-8,peak))
    out=root/c['outputDirectory'];out.mkdir(parents=True,exist_ok=True)
    env=[]
    for i in range(0,n,sr//100):
        block=buses['dialogue'][i:i+sr//100];env.append(round(float(np.sqrt(np.mean(block*block))),6))
    scale=max(.02,float(np.percentile(np.asarray(env)[np.asarray(env)>.005],85)))
    for key,a in buses.items():write(out/(key+'.wav'),a*gain,sr)
    mix*=gain;write(out/'mixed.wav',mix,sr)
    error=float(np.max(np.abs(mix-sum(a*gain for a in buses.values()))))
    report={'scope':'pilot only; listening review pending','start':start,'end':end,'sampleRate':sr,'samples':n,'peak':float(np.max(np.abs(mix))),'gain':gain,'stemSumError':error,'sources':sources,'mixedSha256':sha(out/'mixed.wav')}
    (root/c['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/c['envelope']).write_text(json.dumps({'start':start,'rate':100,'scale':scale,'values':env,'sourceSha256':sha(out/'dialogue.wav'),'kind':'energy opening, not phoneme alignment'}),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['start','end','samples','peak','stemSumError']}))

if __name__=='__main__':main()
