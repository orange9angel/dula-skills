// Local review media must advertise and honor byte ranges for browser seeking.
import fs from 'node:fs';
export function respondFile(req,res,file,contentType='application/octet-stream'){
 const {size}=fs.statSync(file),headers={'Content-Type':contentType,'Cache-Control':'no-store','Accept-Ranges':'bytes'};
 let start=0,end=size-1,status=200;
 if(req.headers.range){
  const m=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range);
  if(!m||(!m[1]&&!m[2])){res.writeHead(416,{...headers,'Content-Range':`bytes */${size}`}).end();return;}
  if(!m[1])start=Math.max(0,size-Number(m[2]));
  else{start=Number(m[1]);if(m[2])end=Math.min(end,Number(m[2]));}
  if(start>=size||start>end||!Number.isSafeInteger(start)||!Number.isSafeInteger(end)){
   res.writeHead(416,{...headers,'Content-Range':`bytes */${size}`}).end();return;
  }
  status=206;headers['Content-Range']=`bytes ${start}-${end}/${size}`;
 }
 headers['Content-Length']=Math.max(0,end-start+1);res.writeHead(status,headers);
 if(req.method==='HEAD'||!size){res.end();return;}
 const stream=fs.createReadStream(file,{start,end});stream.on('error',()=>res.destroy());res.on('close',()=>stream.destroy());stream.pipe(res);
}
