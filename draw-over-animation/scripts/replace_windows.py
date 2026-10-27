"""Assemble several disjoint, frame-aligned drawing repairs in one encode.

Preserve the source AAC stream and verify each boundary against the intended
source. Build fingerprints and deterministic capture reports remain required.
"""
from pathlib import Path
from fractions import Fraction
import argparse,json,subprocess
import numpy as np
from package_pilot import probe,sha,run
from replace_window import video_info,audio_hash,frame

def main():
 p=argparse.ArgumentParser();p.add_argument('--episode',required=True,type=Path);p.add_argument('--config',required=True);a=p.parse_args();root=a.episode.resolve();cfg=json.loads((root/a.config).read_text(encoding='utf-8'))
 source=root/cfg['source'];output=root/cfg['output']
 if sha(source)!=cfg['source_sha256']:raise ValueError('Source changed')
 info=video_info(source);fps=float(Fraction(info['r_frame_rate']));total=int(info['nb_frames']);width=info['width'];height=info['height']
 windows=[];current_sources={};determinism=[]
 configs=[cfg['base_config']]+[w['config'] for w in cfg['patches']]
 for config in configs:
  c=json.loads((root/config).read_text(encoding='utf-8'));board=root/c['pilot']['board'];build=json.loads((board/'build.json').read_text());current_sources.update({v['path']:v['sha256'] for v in build['source']});d=json.loads((board/'determinism.json').read_text());determinism.append({'config':config,'passed':d['passed']})
 for i,w in enumerate(cfg['patches']):
  c=json.loads((root/w['config']).read_text());q=c['pilot'];path=root/q['output'];vi=video_info(path);first=round(q['start']*fps);last=round(q['end']*fps)
  if abs(first-q['start']*fps)>1e-6 or abs(last-q['end']*fps)>1e-6 or not 0<=first<last<=total:raise ValueError('Invalid frame bounds')
  if vi['width']!=width or vi['height']!=height or float(Fraction(vi['r_frame_rate']))!=fps or int(vi['nb_frames'])!=last-first:raise ValueError('Repair media mismatch')
  if windows and first<windows[-1]['last']:raise ValueError('Overlapping or unordered repairs')
  if output.resolve()==path.resolve():raise ValueError('Use a new output file')
  windows.append({'first':first,'last':last,'file':str(path.relative_to(root)),'sha256':sha(path)})
 if output.resolve()==source.resolve():raise ValueError('Use a new output file')
 if not all(sha(root/f)==h for f,h in current_sources.items()):raise ValueError('Render sources changed after capture')
 if not all(d['passed'] for d in determinism):raise ValueError('Non deterministic render')
 filters=[];parts=[];cursor=0;inputs=['-i',source]
 for i,w in enumerate(windows,1):
  inputs+=['-i',root/w['file']]
  if cursor<w['first']:
   tag=f'base{i}';filters.append(f'[0:v]trim=start_frame={cursor}:end_frame={w["first"]},setpts=PTS-STARTPTS[{tag}]');parts.append(f'[{tag}]')
  tag=f'patch{i}';filters.append(f'[{i}:v]trim=start_frame=0:end_frame={w["last"]-w["first"]},setpts=PTS-STARTPTS[{tag}]');parts.append(f'[{tag}]');cursor=w['last']
 if cursor<total:filters.append(f'[0:v]trim=start_frame={cursor}:end_frame={total},setpts=PTS-STARTPTS[tail]');parts.append('[tail]')
 filters.append(''.join(parts)+f'concat=n={len(parts)}:v=1:a=0[v]');output.parent.mkdir(parents=True,exist_ok=True)
 run(*inputs,'-filter_complex',';'.join(filters),'-map','[v]','-map','0:a:0','-c:v','libx264','-preset','medium','-crf',cfg.get('crf',17),'-pix_fmt','yuv420p','-r',fps,'-c:a','copy','-movflags','+faststart',output)
 indices={0,total-1}
 for w in windows:indices.update([max(0,w['first']-1),w['first'],(w['first']+w['last'])//2,w['last']-1,min(total-1,w['last'])])
 samples=[]
 for n in sorted(indices):
  w=next((w for w in windows if w['first']<=n<w['last']),None);ref=root/w['file'] if w else source;rt=(n-w['first'])/fps if w else n/fps
  error=float(np.abs(frame(ref,rt,width,height)-frame(output,n/fps,width,height)).mean());samples.append({'frame':n,'source':str(ref.relative_to(root)),'mean_abs_rgb_error':error,'passed':error<4})
 final=video_info(output);checks={'frames':int(final['nb_frames'])==total,'audio_packets_identical':audio_hash(source,True)==audio_hash(output,True),'audio_pcm_identical':audio_hash(source,False)==audio_hash(output,False),'boundaries':all(s['passed'] for s in samples),'source_current':sha(source)==cfg['source_sha256'],'render_sources_current':all(sha(root/f)==h for f,h in current_sources.items()),'deterministic':all(d['passed'] for d in determinism)}
 report={'passed':all(checks.values()),'checks':checks,'source':cfg['source'],'source_sha256':sha(source),'output':cfg['output'],'output_sha256':sha(output),'frames':total,'fps':fps,'windows':windows,'boundary_samples':samples,'determinism':determinism,'note':'Same-duration multi-window picture repair. Unchanged picture is re-encoded; complete source audio is copied unchanged.'}
 out=root/cfg['report'];out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ['passed','checks','output','frames']},indent=2))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
