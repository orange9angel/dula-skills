"""Replace one isolated voice cue; preserve PCM outside an explicit local window.
Reapply only the ducking delta to existing music/ambience, preserving their edit.
Input is a JSON recipe; all paths resolve under --episode. Existing files stay intact.
"""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess
import numpy as np
import soundfile as sf
from mix_envelopes import smooth_activity
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--episode',type=Path,required=True);ap.add_argument('--config',required=True);a=ap.parse_args();ep=a.episode.resolve();c=json.loads((ep/a.config).read_text(encoding='utf-8'))
 sr=c['sample_rate'];start,end=c['window'];n=round((end-start)*sr);offset=round((c['at']-start)*sr);source=ep/c['source_mix'];output=ep/c['output_mix']
 if output.resolve()==source.resolve():raise ValueError('Use a versioned output')
 if sha(source)!=c['source_sha256']:raise ValueError('Stale source mix')
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(ep/c['voice']),'-af',c.get('filter','anull'),'-ar',str(sr),'-ac','2','-f','f32le','-'])
 voice=np.frombuffer(raw,np.float32).reshape(-1,2).copy();voice*=c['voice_peak']*c['global_gain']/max(float(np.abs(voice).max()),1e-9)
 k=round(.02*sr);voice[:k]*=np.linspace(0,1,k)[:,None];voice[-k:]*=np.linspace(1,0,k)[:,None]
 if offset<0 or offset+len(voice)>n:raise ValueError('Voice exceeds local window')
 stem_dir=ep/c['output_stems'];stem_dir.mkdir(parents=True,exist_ok=True);placed=ep/c['placed_voice'];sf.write(placed,voice,sr,subtype='PCM_24')
 active=[]
 for dur in [c['old_processed_duration'],len(voice)/sr]:
  v=np.zeros(n,np.float32);left=round((c['at']-.13-start)*sr);right=round((c['at']+dur+.15-start)*sr);v[max(0,left):min(n,right)]=1;active.append(smooth_activity(v,sr))
 delta=np.zeros((n,2),np.float64);checks={};provenance={}
 for name,file in c['stems'].items():
  src=ep/file;dst=stem_dir/(name+'_stem.wav');shutil.copyfile(src,dst);provenance[name]={'path':file,'sha256':sha(src)}
  with sf.SoundFile(src) as f:
   if f.samplerate!=sr:raise ValueError('Sample-rate mismatch')
   f.seek(round(start*sr));old=f.read(n,dtype='float64',always_2d=True)
  new=old.copy()
  if name=='dialogue':
   # Recipe asserts this window contains exactly the replaced cue.
   new[:]=0;new[offset:offset+len(voice)]=voice
  elif name in c.get('duck_db',{}):
   db=c['duck_db'][name];new*=10**((-db*(active[1]-active[0]))/20)[:,None]
  delta+=new-old
  with sf.SoundFile(dst,'r+') as f:f.seek(round(start*sr));f.write(new)
  checks[name+'_edges_unchanged']=bool(np.array_equal(new[:sr],old[:sr]) and np.array_equal(new[-sr:],old[-sr:]))
 output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,output)
 with sf.SoundFile(output,'r+') as f:
  f.seek(round(start*sr));mix=f.read(n,dtype='float64',always_2d=True)+delta
  if np.abs(mix).max()>c.get('peak_limit',.8):raise ValueError('Mix clips; revise cue gain')
  f.seek(round(start*sr));f.write(mix)
 checks['outside_pcm_identical']=True
 with sf.SoundFile(source) as old,sf.SoundFile(output) as new:
  at=0
  while True:
   x=old.read(sr,dtype='int32');y=new.read(sr,dtype='int32')
   if not len(x):break
   indices=at+np.arange(len(x));outside=(indices<round(start*sr))|(indices>=round(end*sr))
   checks['outside_pcm_identical'] &= bool(np.array_equal(x[outside],y[outside]))
   at+=len(x)
 report={'passed':all(checks.values()),'checks':checks,'window':[start,end],'old_duration':c['old_processed_duration'],'new_duration':len(voice)/sr,'voice_at':c['at'],'mix_peak_in_window':float(np.abs(mix).max()),'output':c['output_mix'],'sha256':sha(output),'stem_sources':provenance,'recipe':c,'note':'Technical PCM verification only, not emotional listening acceptance.'}
 (ep/c['report']).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ['passed','checks','new_duration','output']}))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
