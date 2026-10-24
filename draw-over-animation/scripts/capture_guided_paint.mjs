import fs from 'node:fs';import path from 'node:path';import {puppeteerFor} from './pipeline.mjs';
const args=process.argv.slice(2),arg=k=>{const i=args.indexOf(k);return i<0?undefined:args[i+1];},root=path.resolve(arg('--episode')??'.');
if(!arg('--config'))throw Error('--config is required');
const cfg=JSON.parse(fs.readFileSync(path.resolve(root,arg('--config')),'utf8'));
const frameCount=(cfg.end-cfg.start)*cfg.fps;if(!(frameCount>0)||Math.abs(frameCount-Math.round(frameCount))>1e-6)throw Error('Capture must contain a positive integer number of frames');
for(let i=0;i<(cfg.keys??[]).length;i++)if(!cfg.keys[i].id||!Number.isFinite(cfg.keys[i].t)||(i&&cfg.keys[i].t<=cfg.keys[i-1].t))throw Error('Keys require IDs and increasing finite times');
const dir=path.resolve(root,cfg.output);fs.mkdirSync(dir,{recursive:true});const b=await puppeteerFor(root).launch({headless:true,args:['--no-sandbox']}),errors=[];
const save=(file,png)=>fs.writeFileSync(path.join(dir,file+'.png'),Buffer.from(png,'base64'));
try{
 const page=await b.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(cfg.url);await page.waitForFunction('window.ready===true');
 for(const key of cfg.keys??[]){const r=await page.evaluate(({t,id})=>window.capturePaintStudy(t,id),key);save(key.id+'_guide',r.image);save(key.id+'_mask',r.mask);}
 const rows=[],count=Math.round((cfg.end-cfg.start)*cfg.fps);
 for(let i=0;i<count;i++){
  const t=cfg.start+i/cfg.fps,lo=cfg.keys?.length?Math.max(0,cfg.keys.findLastIndex(k=>k.t<=t)):null,hi=lo===null?null:Math.min(cfg.keys.length-1,lo+1),ids=cfg.maps===false||lo===null?[]:[...new Set([cfg.keys[lo].id,cfg.keys[hi].id])],tag=String(i).padStart(4,'0');
  const r=await page.evaluate(({t,ids})=>window.capturePaintStudy(t,null,ids),{t,ids});save(tag+'_guide',r.image);save(tag+'_mask',r.mask);for(const id of ids)save(tag+'_to_'+id,r.flow[id]);rows.push({i,t,lo,hi,state:r.state});
  if(i%15===0)console.log(i+'/'+count);if(errors.length)throw Error(errors.join('\n'));
 }
 const checks=[];
 for(const i of cfg.seekFrames??[]){const row=rows[i];if(!row)throw Error('Seek index outside capture');const r=await page.evaluate(t=>window.capturePaintStudy(t),row.t);checks.push({i,equal:Buffer.from(r.image,'base64').equals(fs.readFileSync(path.join(dir,String(i).padStart(4,'0')+'_guide.png')))});}
 if(checks.length)fs.writeFileSync(path.join(dir,'seek.json'),JSON.stringify(checks,null,2));
 fs.writeFileSync(path.join(dir,'capture.json'),JSON.stringify({config:cfg,rows,errors},null,2));
}finally{await b.close();}
