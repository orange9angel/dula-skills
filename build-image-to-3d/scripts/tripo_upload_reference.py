"""Upload one authorized image to the current Tripo WebBridge tab, without generating.

Reads only the explicit image file; never reads browser cookies or credentials.
"""
import argparse
import base64
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image',type=Path)
    ap.add_argument('--session',required=True,help='Reuse the current task WebBridge session')
    ap.add_argument('--daemon-url',default='http://127.0.0.1:10086')
    args=ap.parse_args()
    try:
        path=args.image.resolve()
        if path.stat().st_size>20*1024*1024:raise ValueError('Reference exceeds 20 MB')
        data=path.read_bytes()
        if data.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
        elif data.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
        elif data[:4]==b'RIFF' and data[8:12]==b'WEBP':mime='image/webp'
        else:raise ValueError('Expected PNG, JPEG or WEBP reference')
        payload=json.dumps({'base64':base64.b64encode(data).decode('ascii'),'name':path.name,'mime':mime})
        code="(() => { const payload="+payload+";\n"+"""
if(location.hostname !== 'studio.tripo3d.ai') throw new Error('Current tab is not Tripo Studio');
const input=document.querySelector('input[type=file][accept*="image/png"]');
if(!input) throw new Error('Image reference upload control is not available');
const bytes=Uint8Array.from(atob(payload.base64),c=>c.charCodeAt(0));
const file=new File([bytes],payload.name,{type:payload.mime});
const transfer=new DataTransfer();transfer.items.add(file);input.files=transfer.files;
input.dispatchEvent(new Event('input',{bubbles:true}));
input.dispatchEvent(new Event('change',{bubbles:true}));
return JSON.stringify({name:file.name,size:file.size,generationSubmitted:false});
})()"""
        request={'action':'evaluate','args':{'code':code},'session':args.session}
        req=Request(args.daemon_url.rstrip('/')+'/command',data=json.dumps(request).encode('utf-8'),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=45) as response:result=json.load(response)
        if not result.get('ok'):raise ValueError(result.get('error',{}).get('message','WebBridge failed'))
        result['data']=json.loads(result['data']['value'])
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,URLError) as e:
        print(json.dumps({'ok':False,'error':{'code':'upload_failed','message':str(e)}},ensure_ascii=False));return 1


if __name__=='__main__':sys.exit(main())
