// Same-camera region study: pixel boundary audit plus a full-body A/B with
// separate portrait diagnostics. Episode-specific rig access stays in viewer.
import fs from 'node:fs';
import path from 'node:path';
import {puppeteerFor} from './pipeline.mjs';
const args=process.argv.slice(2),arg=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(arg('--episode','.')),cfg=JSON.parse(fs.readFileSync(path.resolve(root,arg('--config')),'utf8'));
const dir=path.resolve(root,cfg.output);fs.mkdirSync(path.join(dir,'frames'),{recursive:true});
const browser=await puppeteerFor(root).launch({headless:true,args:['--no-sandbox']});
const frames=[],errors=[];
try{
 const page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.setViewport({width:cfg.width,height:cfg.height,deviceScaleFactor:1});
 await page.goto(cfg.url);await page.waitForFunction('window.ready===true',{timeout:30000});
 const count=Math.round((cfg.end-cfg.start)*cfg.fps);
 for(let i=0;i<count;i++){
  const t=cfg.start+i/cfg.fps,save=cfg.samples.some(v=>Math.abs(t-v)<.5/cfg.fps);
  const result=await page.evaluate(async(t,cfg)=>{
   const pair=window.renderRegionPair(t),portraits=[window.renderRegionPortrait(t,0),window.renderRegionPortrait(t,1)];
   const load=async b=>{const im=new Image();im.src='data:image/png;base64,'+b;await im.decode();return im;};
   const [a,b,m,pa,pb]=await Promise.all([pair.base,pair.paint,pair.mask,...portraits].map(load));
   const canvas=document.createElement('canvas');canvas.width=cfg.width;canvas.height=cfg.height;const ctx=canvas.getContext('2d',{willReadFrequently:true});
   const pixels=im=>{ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(im,0,0);return ctx.getImageData(0,0,canvas.width,canvas.height).data;};
   const ap=pixels(a),bp=pixels(b),mp=pixels(m),allowed=new Uint8Array(cfg.width*cfg.height);
   // Include fractional MSAA coverage: a thin hair edge may never reach 50%.
   for(let y=0;y<cfg.height;y++)for(let x=0;x<cfg.width;x++)if(mp[(y*cfg.width+x)*4]>0){
    for(let dy=-cfg.maskPadding;dy<=cfg.maskPadding;dy++)for(let dx=-cfg.maskPadding;dx<=cfg.maskPadding;dx++){
     const xx=x+dx,yy=y+dy;if(xx>=0&&xx<cfg.width&&yy>=0&&yy<cfg.height)allowed[yy*cfg.width+xx]=1;
    }
   }
   let outsideChanged=0,outsideAboveOne=0,outsideMax=0,insideChanged=0;const outsideExamples=[];
   for(let p=0;p<allowed.length;p++){
    const k=p*4,d=Math.max(Math.abs(ap[k]-bp[k]),Math.abs(ap[k+1]-bp[k+1]),Math.abs(ap[k+2]-bp[k+2]));
    if(allowed[p]){if(d)insideChanged++;}else if(d){outsideChanged++;outsideMax=Math.max(outsideMax,d);if(d>1)outsideAboveOne++;if(outsideExamples.length<10)outsideExamples.push({x:p%cfg.width,y:Math.floor(p/cfg.width),delta:d});}
   }
   // Each panel keeps the full source height, so feet are not shrunk to a thumbnail.
   const panel=cfg.width/2,headX=(pair.headScreen[0]*.5+.5)*cfg.width,cropX=Math.max(0,Math.min(cfg.width-panel,headX-panel/2));
   ctx.fillStyle='#18212f';ctx.fillRect(0,0,cfg.width,cfg.height);
   [a,b].forEach((im,j)=>{ctx.drawImage(im,cropX,0,panel,cfg.height,j*panel,0,panel,cfg.height);ctx.fillStyle='#18212f';ctx.fillRect(j*panel,0,panel,42);ctx.fillStyle='#ffffff';ctx.font='22px Microsoft YaHei, sans-serif';ctx.fillText(cfg.labels[j],j*panel+14,29);});
   [pa,pb].forEach((im,j)=>{ctx.drawImage(im,j*panel+12,52,220,220);ctx.fillStyle='#18212f';ctx.fillRect(j*panel+12,272,220,28);ctx.fillStyle='#ffffff';ctx.font='14px Microsoft YaHei, sans-serif';ctx.fillText('同角度头部检查',j*panel+22,292);});
   return{comparison:canvas.toDataURL('image/png').split(',')[1],base:pair.base,paint:pair.paint,mask:pair.mask,portraits,
    audit:{t,outsideChanged,outsideAboveOne,outsideMax,outsideExamples,insideChanged,stateIdentical:JSON.stringify(pair.state)===JSON.stringify(pair.baseState)}};
  },t,cfg);
  if(errors.length)throw Error(errors.join('\n'));
  const tag=String(i).padStart(4,'0');fs.writeFileSync(path.join(dir,'frames',tag+'.png'),Buffer.from(result.comparison,'base64'));
  if(save||result.audit.outsideChanged){for(const key of ['base','paint','mask'])fs.writeFileSync(path.join(dir,tag+'_'+key+'.png'),Buffer.from(result[key],'base64'));for(let j=0;j<2;j++)fs.writeFileSync(path.join(dir,tag+'_portrait'+j+'.png'),Buffer.from(result.portraits[j],'base64'));
   const hasLegs=await page.evaluate(()=>typeof window.renderLegDiagnostic==='function');
   if(hasLegs){const leg=await page.evaluate(t=>window.renderLegDiagnostic(t),t);fs.writeFileSync(path.join(dir,tag+'_legs.png'),Buffer.from(leg.image,'base64'));result.audit.feet=leg.feet;result.audit.pose=leg.state;}
  }
  frames.push(result.audit);if(i%15===0)console.log(JSON.stringify({frame:i,t,...result.audit,pose:undefined}));
 }
 const report={config:cfg,frames,errors,passed:frames.every(f=>f.outsideChanged===0&&f.stateIdentical),note:'Numerical boundary/state audit only. Portrait insets are diagnostic renders, not additional shots.'};
 fs.writeFileSync(path.join(dir,'audit.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({output:dir,passed:report.passed,frames:frames.length,outsideMax:Math.max(...frames.map(f=>f.outsideMax))}));
 if(!report.passed)process.exitCode=1;
}finally{await browser.close();}
