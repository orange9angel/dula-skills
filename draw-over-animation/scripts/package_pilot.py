"""Shared before/after packaging and validation; all content comes from config."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import numpy as np

def run(*args):
    subprocess.run(['ffmpeg','-hide_banner','-v','error','-y',*map(str,args)],check=True)

def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def probe(file):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'stream=codec_type,width,height,r_frame_rate,nb_frames,duration:format=duration',
        '-of','json',str(file)],text=True))

def bounds(root, pilot):
    if not pilot.get('timeline'):
        return pilot['start'],pilot['end']
    spans=re.findall(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})',
                     (root/pilot['timeline']).read_text(encoding='utf-8'))
    def sec(v):
        h,m,s=map(float,v.replace(',','.').split(':'));return 3600*h+60*m+s
    times=[(sec(a),sec(b)) for a,b in spans]
    if not times or any(b<=a or (i and a!=times[i-1][1]) for i,(a,b) in enumerate(times)):
        raise ValueError('Timeline is empty or non-contiguous')
    return times[0][0],times[-1][1]

def pcm(file,start,duration):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),
        '-i',str(file),'-t',str(duration),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1']),dtype=np.float32)

def audio_check(source,file,start,duration):
    a,b=pcm(source,start,duration),pcm(file,0,duration)
    n=min(len(a),len(b));a,b=a[:n],b[:n]
    if n<320:raise ValueError('Too little audio for alignment check')
    scores=[]
    for lag in range(-160,161):
        x,y=(a[lag:],b[:n-lag]) if lag>=0 else (a[:n+lag],b[-lag:])
        denominator=float(np.linalg.norm(x)*np.linalg.norm(y))
        corr=float(np.dot(x,y)/denominator) if denominator else (1.0 if np.array_equal(x,y) else 0.0)
        scores.append((corr,-abs(lag),lag))
    corr,_,lag=max(scores)
    return dict(correlation=corr,offset_ms=lag/16,passed=corr>.98 and abs(lag)<=16)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode',required=True);parser.add_argument('--config',required=True)
    args=parser.parse_args();root=Path(args.episode).resolve();cfg=json.loads((root/args.config).read_text(encoding='utf-8'))
    if cfg['schema']!='draw-over-pipeline-v1':raise ValueError('Unsupported pipeline schema')
    p,k=cfg['pilot'],cfg['package'];start,end=bounds(root,p);duration=end-start
    source,pilot,compare=root/cfg['source']['video'],root/p['output'],root/k['comparison']
    board=root/p['board'];board.mkdir(parents=True,exist_ok=True);compare.parent.mkdir(parents=True,exist_ok=True)
    assert sha(source)==cfg['source']['sha256'],'Accepted baseline changed'
    width,height=p['width'],p['height'];header=k.get('headerHeight',48)
    font=Path(k['font']).as_posix().replace(':',r'\:')
    if "'" in font:raise ValueError('Use a font path without apostrophes')
    # textfile avoids shell/filter expansion of labels; structured subprocess
    # argv keeps Unicode, spaces and literal punctuation intact.
    labels=[]
    for i,label in enumerate(k['labels']):
        file=board/f'comparison_label_{i}.txt';file.write_text(label,encoding='utf-8')
        labels.append(file.as_posix().replace(':',r'\:'))
    filters=(f"[0:v]setpts=PTS-STARTPTS,fps={p['fps']},scale={width}:{height}[a];"
        f"[1:v]setpts=PTS-STARTPTS,fps={p['fps']}[b];[a][b]hstack=inputs=2,pad={width*2}:{height+header}:0:{header}:color=0x121723,"
        f"drawtext=fontfile='{font}':textfile='{labels[0]}':expansion=none:fontcolor=white:fontsize={k.get('fontSize',27)}:x=28:y=10,"
        f"drawtext=fontfile='{font}':textfile='{labels[1]}':expansion=none:fontcolor=0xffd99b:fontsize={k.get('fontSize',27)}:x={width+28}:y=10[v]")
    run('-ss',start,'-t',duration,'-i',source,'-i',pilot,'-filter_complex',filters,'-map','[v]','-map','1:a:0',
        '-c:v','libx264','-preset','medium','-crf',18,'-r',p['fps'],'-pix_fmt','yuv420p','-c:a','copy','-t',duration,'-movflags','+faststart',compare)
    report=dict(source=cfg['source']['video'],source_sha256=cfg['source']['sha256'],start=start,duration=duration,
                scope='configured shot-specific pilot; not full-episode integration',outputs=[])
    for file in [pilot,compare]:
        media,sound=probe(file),audio_check(source,file,start,duration)
        video=next(s for s in media['streams'] if s['codec_type']=='video')
        assert int(video['nb_frames'])==round(duration*p['fps']) and sound['passed'],(media,sound)
        report['outputs'].append(dict(file=str(file.relative_to(root)).replace('\\','/'),sha256=sha(file),media=media,audio=sound))
    for sheet in k.get('sheets',[]):
        every=sheet['everyFrames'];assert isinstance(every,int) and every>0
        vf=(f"select=not(mod(n\\,{every})),scale={sheet.get('width',384)}:-2,drawtext=fontfile='{font}':"
            "text='%{pts\\:hms}':fontcolor=white:fontsize=15:x=8:y=7:box=1:boxcolor=black@0.7,"
            f"tile={sheet['layout']}")
        run('-ss',sheet['start'],'-t',sheet['duration'],'-i',pilot,'-vf',vf,'-frames:v',1,'-update',1,board/f"{sheet['name']}.jpg")
    motion=[]
    for item in cfg.get('bake',{}).get('windows',[]):
        file=root/item['output'];data=json.loads(file.read_text(encoding='utf-8'))
        assert len(data['frames'])==round((data['end']-data['start'])*data['fps'])+1
        for name,digest in data['source'].items():assert sha(root/name)==digest,f'Stale bake: {name}'
        coords=[v for f in data['frames'] for a in f['actors'].values() for v in a['world'].values()]
        assert np.isfinite(coords).all()
        motion.append(dict(id=item['id'],frames=len(data['frames']),sha256=sha(file),finite=True,
                           consumed_by_pilot=item.get('consumedByPilot',False),note=item.get('note','')))
    report['motion']=motion;report['determinism']=json.loads((board/'determinism.json').read_text())
    assert report['determinism']['passed']
    report['technical_passed']=True;report['visual_review']='See episode review; technical checks are not visual approval'
    (board/'delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,audio=report['outputs'][0]['audio'],files=[str(pilot),str(compare)]),ensure_ascii=False))

if __name__=='__main__':main()
