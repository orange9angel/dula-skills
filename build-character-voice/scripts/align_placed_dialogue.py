"""Align a known short line from its final placed PCM, retaining one timeline origin."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
import numpy as np
from pypinyin import lazy_pinyin,Style
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer
SKILLS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SKILLS.parent/'dula-assets'/'lib'/'audio'))
from known_text_alignment import align_text

p=argparse.ArgumentParser(__doc__);p.add_argument('episode',type=Path);p.add_argument('--config',required=True);a=p.parse_args();root=a.episode.resolve();cfg=json.loads((root/a.config).read_text(encoding='utf-8'))
source=root/cfg['source'];tl=json.loads((root/cfg['timeline']).read_text(encoding='utf-8'));cues={s['id']:s for s in tl['segments']}
model=WhisperModel(cfg.get('model','base'),device='cpu',compute_type='int8',local_files_only=True)
make_tokenizer=lambda:Tokenizer(model.hf_tokenizer,model.model.is_multilingual,task='transcribe',language='zh')
clips=[]
for line in cfg['lines']:
    cue=cues[line['cue']];zero=cue['start']+line.get('offset',0);duration=line['duration'];local=zero-cfg['sourceStart']
    crop=root/'tmp'/(line['cue']+'_placed.wav');crop.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-y','-v','error','-ss',str(local),'-t',str(duration),'-i',str(source),'-ar','16000','-ac','1',str(crop)],check=True)
    text=re.sub(r'[^\u4e00-\u9fff]','',cue['text']);chars,actual=align_text(model,make_tokenizer,crop,text)
    raw=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(crop),'-f','f32le','-ac','1','-ar','16000','pipe:1']),dtype='<f4')
    hop=160;env=np.sqrt(np.mean(raw[:len(raw)//hop*hop].reshape(-1,hop)**2,axis=1)+1e-12)
    for i,c in enumerate(chars):
        # Keep the DTW order and remove overlaps before adding the placement origin.
        if i+1<len(chars):c['end']=min(c['end'],chars[i+1]['start'])
        if c['end']<c['start']:raise ValueError('Non-monotonic alignment')
        lo=max(0,round(c['start']*100));hi=min(len(env),round(c['end']*100))
        active=np.flatnonzero(env[lo:hi]>max(.003,float(np.percentile(env,85))*.05))
        if len(active) and active[0]>=6:
            c['rawStart']=c['start'];c['start']=max(c['start'],(lo+int(active[0]))/100-.03)
            c['startAdjustment']='remove a DTW-assigned leading silence; retain 30ms anticipation'
        # A long DTW word can begin with the previous vowel's tail, then include
        # the whole sentence pause. Find the new speech after that interior gap.
        if c['end']-c['start']>.5:
            audible=env[lo:hi]>max(.003,float(np.percentile(env,85))*.05);gap=0
            for j,on in enumerate(audible):
                if on:
                    if gap>=12:
                        c.setdefault('rawStart',c['start']);c['start']=max(c['start'],(lo+j)/100-.03)
                        c['startAdjustment']='remove interior sentence pause assigned to next word by DTW'
                    gap=0
                else:gap+=1
        c.update(initial=lazy_pinyin(c['ch'],style=Style.INITIALS,strict=False)[0],final=lazy_pinyin(c['ch'],style=Style.FINALS,strict=False)[0])
        c['start']=round(c['start']+zero,4);c['end']=round(c['end']+zero,4)
    clips.append({'cue':line['cue'],'character':cue['character'],'text':text,'start':zero,'duration':actual,'chars':chars,'energyRate':100,'energy':[round(float(x),6) for x in env]})
result={'method':'known-text Whisper DTW on isolated final placed dialogue PCM; ASR content checked separately','source':cfg['source'],'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sourceStart':cfg['sourceStart'],'storySha256':hashlib.sha256((root/'script.story').read_bytes()).hexdigest(),'clips':clips}
(root/cfg['output']).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'clips':len(clips),'characters':sum(len(c['chars']) for c in clips)}))
