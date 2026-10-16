"""Audio-only model observation using an existing DashScope credential; advisory."""
from pathlib import Path
import argparse, base64, hashlib, json, os, urllib.request

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio',type=Path);p.add_argument('--prompt',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--env-dir',type=Path)
    a=p.parse_args()
    if a.env_dir:
        for f in a.env_dir.glob('.env*'):
            if not f.is_file():continue
            for line in f.read_text(encoding='utf-8-sig',errors='ignore').splitlines():
                line=line.strip().removeprefix('export ')
                if not line or line.startswith('#') or '=' not in line:continue
                k,v=line.split('=',1)
                if k.strip()=='DASHSCOPE_API_KEY':os.environ.setdefault(k.strip(),v.strip().strip('\"\''))
    key=os.environ.get('DASHSCOPE_API_KEY')
    if not key:raise SystemExit('Audio-review credential unavailable')
    data=a.audio.read_bytes();fmt=a.audio.suffix[1:]
    prompt=a.prompt.read_text(encoding='utf-8-sig')
    payload={'model':'qwen3-omni-flash','modalities':['text'],'stream':True,
        'messages':[{'role':'user','content':[
            {'type':'input_audio','input_audio':{'data':f'data:audio/{fmt};base64,'+base64.b64encode(data).decode(),'format':fmt}},
            {'type':'text','text':prompt}]}]}
    req=urllib.request.Request('https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    answer=''
    with urllib.request.urlopen(req,timeout=160) as response:
        for line in response:
            if not line.startswith(b'data:'):continue
            raw=line[5:].strip()
            if raw==b'[DONE]':break
            event=json.loads(raw)
            if 'error' in event:raise RuntimeError('Audio reviewer returned an error')
            for choice in event.get('choices',[]):answer+=choice.get('delta',{}).get('content') or ''
    if not answer.strip():raise RuntimeError('Empty audio review')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps({'model':payload['model'],'audio':str(a.audio.resolve()),
        'sha256':hashlib.sha256(data).hexdigest(),'prompt':prompt,'observation':answer,
        'limit':'Model audio observation only; not human listening or user acceptance.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(answer)

if __name__=='__main__':main()
