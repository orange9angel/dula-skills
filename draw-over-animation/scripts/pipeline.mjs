// Shared draw-over production runner. All episode names, windows, viewers,
// source files and rig accessors come from the selected episode configuration.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {pathToFileURL,fileURLToPath} from 'node:url';

const sha=b=>createHash('sha256').update(b).digest('hex');
const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(data,null,2));};
export function timelineBounds(file){
 const seconds=s=>{const [h,m,v]=s.replace(',','.').split(':').map(Number);return h*3600+m*60+v;};
 const spans=[...fs.readFileSync(file,'utf8').matchAll(/(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})/g)].map(m=>[seconds(m[1]),seconds(m[2])]);
 if(!spans.length||spans.some((s,i)=>s[1]<=s[0]||(i&&s[0]!==spans[i-1][1])))throw Error(`Invalid or non-contiguous timeline: ${file}`);
 return{start:spans[0][0],end:spans.at(-1)[1]};
}
export function puppeteerFor(root){
 try{return createRequire(path.join(root,'package.json'))('puppeteer');}catch{}
 for(let dir=root;;dir=path.dirname(dir)){
  const pkg=path.join(dir,'node_modules/dula-engine/package.json');
  if(fs.existsSync(pkg))return createRequire(pkg)('puppeteer');
  if(path.dirname(dir)===dir)break;
 }
 throw Error('Install Puppeteer in this episode/workspace or its dula-engine dependency');
}
function range(root,w,fps){
 const r=w.timeline?timelineBounds(path.resolve(root,w.timeline)):{start:w.start,end:w.end};
 const n=(r.end-r.start)*fps;
 if(!Number.isFinite(n)||n<=0||Math.abs(n-Math.round(n))>1e-6)throw Error('Window must contain a positive integer number of frames');
 return{...r,frames:Math.round(n)};
}
function finite(value){if(typeof value==='number'&&!Number.isFinite(value))throw Error('Non-finite motion value');if(value&&typeof value==='object')Object.values(value).forEach(finite);}

export async function runPipeline({episode,config,step,render=false}){
 const root=path.resolve(episode),configFile=path.resolve(root,config),cfg=JSON.parse(fs.readFileSync(configFile,'utf8'));
 if(cfg.schema!=='draw-over-pipeline-v1')throw Error('Unsupported pipeline schema');
 const p=cfg.pilot,fps=p.fps;
 if(!(fps>0&&p.width>0&&p.height>0))throw Error('Invalid frame rate/size');
 const abs=f=>path.resolve(root,f),url=f=>new URL(f,cfg.baseUrl).href,board=abs(p.board),r=range(root,p,fps);
 const fingerprints=files=>Object.fromEntries(files.map(f=>[f,sha(fs.readFileSync(abs(f)))]));
 if(cfg.runtime){
  const dir=abs(cfg.runtime.directory),manifest=path.join(dir,'shared-runtime.json');
  const previous=fs.existsSync(manifest)?JSON.parse(fs.readFileSync(manifest,'utf8')):{};
  const assets=fileURLToPath(new URL('../assets/',import.meta.url)),next={};fs.mkdirSync(dir,{recursive:true});
  for(const name of fs.readdirSync(assets).filter(n=>/\.(mjs|js)$/.test(n))){
   const source=fs.readFileSync(path.join(assets,name)),target=path.join(dir,name),digest=sha(source);
   if(fs.existsSync(target)){const old=sha(fs.readFileSync(target));if(old!==digest&&old!==previous[name])throw Error(`Generated runtime has local edits: ${target}. Move shared changes into the skill source before preparing.`);}
   fs.writeFileSync(target,source);next[name]=digest;
  }
  write(manifest,next);
 }
 if(step==='prepare'){console.log(JSON.stringify({prepared:cfg.runtime?.directory??null}));return;}
 if(step==='package'||step==='integrate'){
  const script=fileURLToPath(new URL(step==='package'?'./package_pilot.py':'./replace_window.py',import.meta.url));
  const proc=spawn('python',[script,'--episode',root,'--config',configFile],{stdio:'inherit',windowsHide:true});
  const [code]=await once(proc,'close');if(code!==0)throw Error(`Packaging exited ${code}`);return;
 }
 if(!['bake','render','probe'].includes(step))throw Error(`Unknown step: ${step}`);
 const browser=await puppeteerFor(root).launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.setViewport({width:p.width,height:p.height,deviceScaleFactor:1});
  await page.goto(url(step==='bake'?cfg.bake.viewer:p.viewer));
  try{await page.waitForFunction('window.ready===true',{timeout:30000});}
  catch(error){throw Error(`Viewer did not become ready: ${errors.join('; ')||error.message}`);}
  if(step==='bake'){
   const spec=cfg.bake,adapter=await import(pathToFileURL(abs(spec.adapter)).href);
   if(typeof adapter.capture!=='function')throw Error('Bake adapter must export capture(t, context)');
   for(const w of spec.windows){
    const q=range(root,w,fps),frames=[];
    for(let frame=0;frame<=q.frames;frame++){
     const t=q.start+frame/fps,data=await page.evaluate(adapter.capture,t,{width:p.width,height:p.height});finite(data);
     if(!data?.actors||!data?.camera)throw Error('Bake adapter must return actors and camera');
     frames.push({frame,t,...data});
    }
    const data={schema:'dula-motion-2d-pilot-v1',id:w.id,start:q.start,end:q.end,fps,
     source:fingerprints(spec.sourceFiles),projection:`world + actual source camera ${p.width}x${p.height}; art camera may differ`,
     contactNote:'null means source contact metadata is unavailable, not a successful contact test',frames};
    write(abs(w.output),data);console.log(JSON.stringify({id:w.id,frames:frames.length,out:abs(w.output)}));
   }
  }else if(step==='probe'){
   const adapter=await import(pathToFileURL(abs(cfg.probe.adapter)).href);
   const report=await page.evaluate(adapter.probe);finite(report);write(abs(cfg.probe.output),report);console.log(JSON.stringify(report));
   if(report.passed!==true)throw Error('Episode motion/anchor probe failed');
  }else{
   fs.mkdirSync(board,{recursive:true});
   const capture=async t=>{const a=await page.evaluate(t=>window.renderAt(t),t);if(errors.length)throw Error(errors.join('\n'));if(!a?.image)throw Error('renderAt must return a base64 PNG image');const b=Buffer.from(a.image,'base64');if(b.subarray(1,4).toString()!=='PNG')throw Error('Lossless PNG output required');return{b,state:a.state??{t}};};
   const samples=[];
   for(const t of p.samples??[]){if(t<r.start||t>=r.end)throw Error(`Sample outside pilot: ${t}`);const a=await capture(t);fs.writeFileSync(path.join(board,`t${String(t).replace('.','_')}.png`),a.b);samples.push({...a.state,sha256:sha(a.b)});}
   write(path.join(board,'samples.json'),samples);
   const files=[...p.sourceFiles];for(const folder of p.assetDirectories??[])for(const f of fs.readdirSync(abs(folder)))if(f.endsWith('.png'))files.push(`${folder}/${f}`);
   const shared=fs.readdirSync(import.meta.dirname).filter(f=>/\.(mjs|py)$/.test(f)).map(f=>({path:f,sha256:sha(fs.readFileSync(path.join(import.meta.dirname,f)))}));
   write(path.join(board,'build.json'),{source:Object.entries(fingerprints(files)).map(([path,sha256])=>({path,sha256})),pipeline:{config:cfg,shared},...r,fps,errors});
   if(render){
    if(sha(fs.readFileSync(abs(cfg.source.video)))!==cfg.source.sha256)throw Error('Accepted source video changed');
    const output=abs(p.output);fs.mkdirSync(path.dirname(output),{recursive:true});
    const audio=p.audioCopy?['-c:a','copy']:['-c:a','aac','-b:a','192k'];
    const enc=spawn('ffmpeg',['-y','-v','error','-f','image2pipe','-framerate',String(fps),'-vcodec','png','-i','pipe:0','-ss',String(r.start),'-t',String(r.end-r.start),'-i',abs(cfg.source.video),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','medium','-crf',String(p.crf??17),'-pix_fmt','yuv420p',...audio,'-t',String(r.end-r.start),'-movflags','+faststart',output],{stdio:['pipe','inherit','inherit'],windowsHide:true});
    const done=once(enc,'close'),frames=new Map();
    try{
     for(let i=0;i<r.frames;i++){const t=r.start+i/fps,a=await capture(t);if(!enc.stdin.write(a.b))await once(enc.stdin,'drain');if(i%(p.hashEvery??15)===0||i===r.frames-1)frames.set(t,sha(a.b));if(i%(fps*2)===0)console.log(`${i}/${r.frames}`);}
     enc.stdin.end();const [code]=await done;if(code!==0)throw Error(`Encoder exited ${code}`);
    }catch(error){enc.stdin.destroy();enc.kill();throw error;}
    const checks=[];for(const [t,s]of [...frames].reverse()){const a=await capture(t);checks.push({t,equal:s===sha(a.b)});}
    for(const t of p.repeatSamples??[]){const a=await capture(t),b=await capture(t);checks.push({t,repeat:true,equal:sha(a.b)===sha(b.b)});}
    const report={passed:checks.every(c=>c.equal),checks};write(path.join(board,'determinism.json'),report);if(!report.passed)throw Error('Sequential/seek pixel mismatch');
    console.log(JSON.stringify({output,frames:r.frames,checks:checks.length,errors}));
   }
  }
  if(errors.length)throw Error(errors.join('\n'));
 }finally{await browser.close();}
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2),value=k=>{const i=args.indexOf(k);if(i<0||!args[i+1])throw Error(`Missing ${k}`);return args[i+1];};
 if(args.includes('--help'))console.log('node pipeline.mjs --episode PATH --config CONFIG.json --step prepare|bake|render|package|probe|integrate [--render]');
 else await runPipeline({episode:value('--episode'),config:value('--config'),step:value('--step'),render:args.includes('--render')});
}
