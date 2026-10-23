"""Insert an approved same-duration drawing window into the source episode.

Picture is re-encoded; the original complete audio stream is copied. Frame
counts, insertion boundary samples and full audio hashes are verified.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import json
import subprocess
import numpy as np
from package_pilot import bounds,probe,run,sha

def video_info(file):
    return next(s for s in probe(file)['streams'] if s['codec_type']=='video')

def audio_hash(file,copy):
    args=['ffmpeg','-v','error','-i',str(file),'-map','0:a:0','-vn']
    args+=['-c:a','copy'] if copy else ['-c:a','pcm_s16le']
    args+=['-f','hash','-hash','sha256','pipe:1']
    return subprocess.check_output(args,text=True).strip()

def frame(file,t,width,height):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(file),'-frames:v','1',
        '-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
    image=np.frombuffer(data,dtype=np.uint8)
    if image.size!=width*height*3:raise ValueError(f'Cannot read frame at {t}: {file}')
    return image.astype(np.int16)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--episode',required=True);parser.add_argument('--config',required=True)
    args=parser.parse_args();root=Path(args.episode).resolve();cfg=json.loads((root/args.config).read_text(encoding='utf-8'))
    p,k=cfg['pilot'],cfg['integration'];source=root/cfg['source']['video'];replacement=root/p['output'];output=root/k['output']
    if output.resolve() in [source.resolve(),replacement.resolve()]:raise ValueError('Use a new delivery filename')
    if sha(source)!=cfg['source']['sha256']:raise ValueError('Accepted source video changed')
    source_info,pilot_info=video_info(source),video_info(replacement);fps=float(Fraction(source_info['r_frame_rate']))
    if fps!=p['fps'] or pilot_info['r_frame_rate']!=source_info['r_frame_rate']:raise ValueError('Insertion requires matching frame rates')
    for key in ['width','height']:
        if source_info[key]!=pilot_info[key]:raise ValueError('Insertion requires matching frame dimensions')
    start,end=bounds(root,p);first,last=round(start*fps),round(end*fps);total=int(source_info['nb_frames'])
    if abs(start*fps-first)>1e-6 or abs(end*fps-last)>1e-6 or not 0<=first<last<=total:raise ValueError('Window is not frame-aligned or exceeds source')
    if int(pilot_info['nb_frames'])!=last-first:raise ValueError('Replacement duration mismatch')
    filters=[];parts=[]
    if first:
        filters.append(f'[0:v]trim=start_frame=0:end_frame={first},setpts=PTS-STARTPTS[before]');parts.append('[before]')
    filters.append(f'[1:v]trim=start_frame=0:end_frame={last-first},setpts=PTS-STARTPTS[insert]');parts.append('[insert]')
    if last<total:
        filters.append(f'[0:v]trim=start_frame={last}:end_frame={total},setpts=PTS-STARTPTS[after]');parts.append('[after]')
    filters.append(''.join(parts)+f'concat=n={len(parts)}:v=1:a=0[v]')
    output.parent.mkdir(parents=True,exist_ok=True)
    run('-i',source,'-i',replacement,'-filter_complex',';'.join(filters),'-map','[v]','-map','0:a:0',
        '-c:v','libx264','-preset','medium','-crf',k.get('crf',17),'-pix_fmt','yuv420p','-r',fps,
        '-c:a','copy','-movflags','+faststart',output)
    info=video_info(output)
    if int(info['nb_frames'])!=total:raise ValueError('Integrated episode frame count changed')
    packet_equal=audio_hash(source,True)==audio_hash(output,True)
    pcm_equal=audio_hash(source,False)==audio_hash(output,False)
    checks=[]
    for index in sorted({max(0,first-1),first,(first+last)//2,last-1,min(total-1,last),total-1}):
        inside=first<=index<last;expected=replacement if inside else source;t=(index-first)/fps if inside else index/fps
        a=frame(expected,t,p['width'],p['height']);b=frame(output,index/fps,p['width'],p['height'])
        error=float(np.abs(a-b).mean());checks.append(dict(frame=index,source='replacement' if inside else 'original',mean_abs_rgb_error=error,passed=error<4))
    report=dict(source=cfg['source']['video'],source_sha256=cfg['source']['sha256'],replacement=p['output'],replacement_sha256=sha(replacement),
        output=k['output'],output_sha256=sha(output),window={'start':start,'end':end,'first_frame':first,'end_frame_exclusive':last},
        frames=total,fps=fps,media=probe(output),audio_packets_identical=packet_equal,audio_pcm_identical=pcm_equal,
        boundary_samples=checks,note='Picture outside the insertion comes from the source and is re-encoded; no pixel-identical claim',
        passed=packet_equal and pcm_equal and all(c['passed'] for c in checks))
    report_file=root/k['report'];report_file.parent.mkdir(parents=True,exist_ok=True);report_file.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not report['passed']:raise ValueError(f'Integration verification failed; see {report_file}')
    print(json.dumps(dict(output=str(output),frames=total,audio_packets_identical=packet_equal,audio_pcm_identical=pcm_equal,passed=True)))

if __name__=='__main__':main()
