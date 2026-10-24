"""Decode exact frame indices and label ordered sheets; no visual grading."""
import argparse, hashlib, json, subprocess
from fractions import Fraction
from pathlib import Path
from PIL import Image, ImageDraw

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cfg=json.loads(a.config.read_text(encoding='utf-8'));a.output.mkdir(parents=True,exist_ok=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=r_frame_rate,nb_frames','-of','json',str(a.source)]))['streams'][0]
    fps=float(Fraction(info['r_frame_rate']));offset=cfg.get('timeOffset',0)
    frames=sorted({round((t-offset)*fps) for g in cfg['groups'].values() for t in g['times']})
    if not frames or min(frames)<0 or max(frames)>=int(info['nb_frames']):raise ValueError('Requested time outside source')
    select='+'.join(f'eq(n\\,{f})' for f in frames)
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(a.source),'-vf','select='+select,'-vsync','0',str(a.output/'decoded_%05d.png')],check=True)
    files={}
    for i,f in enumerate(frames,1):
        source=a.output/f'decoded_{i:05d}.png';target=a.output/f'n{f:06d}.png';source.replace(target);files[f]=target
    groups={}
    for name,g in cfg['groups'].items():
        cols=g.get('columns',3);tw=g.get('width',480);first=Image.open(files[round((g['times'][0]-offset)*fps)])
        size=(g['crop'][2]-g['crop'][0],g['crop'][3]-g['crop'][1]) if 'crop' in g else first.size
        th=round(tw*size[1]/size[0]);sheet=Image.new('RGB',(tw*cols,(th+24)*((len(g['times'])+cols-1)//cols)),(24,24,30));draw=ImageDraw.Draw(sheet);rows=[]
        for i,t in enumerate(g['times']):
            f=round((t-offset)*fps);im=Image.open(files[f]).convert('RGB')
            if 'crop' in g:im=im.crop(g['crop'])
            x=i%cols*tw;y=i//cols*(th+24);sheet.paste(im.resize((tw,th)),(x,y));draw.text((x+5,y+th+4),f'{offset+f/fps:.3f}s / frame {f}',fill='white')
            rows.append({'time':offset+f/fps,'frame':f,'path':files[f].name,'sha256':digest(files[f])})
        path=a.output/(name+'.jpg');sheet.save(path,quality=93);groups[name]={'sheet':path.name,'sha256':digest(path),'frames':rows}
    manifest={'source':str(a.source.resolve()),'sourceSha256':digest(a.source),'fps':fps,'timeOffset':offset,'groups':groups,'viewingMethod':'ordered_frames','note':'Extraction is not an observation; record visual findings only after viewing.'}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps({'frames':len(frames),'groups':len(groups),'output':str(a.output)}))

if __name__=='__main__':main()
