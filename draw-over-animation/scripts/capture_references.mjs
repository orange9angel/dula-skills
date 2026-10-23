// Generic source-pose capture. Rig access and framing stay in the episode adapter.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {puppeteerFor} from './pipeline.mjs';
const args=process.argv.slice(2),arg=k=>args[args.indexOf(k)+1];
const root=path.resolve(arg('--episode')),cfg=JSON.parse(fs.readFileSync(path.resolve(root,arg('--config')),'utf8'));
const adapter=await import(pathToFileURL(path.resolve(root,cfg.adapter)).href),browser=await puppeteerFor(root).launch({headless:true,args:['--no-sandbox']});
try{const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewport({width:cfg.width,height:cfg.height});await page.goto(cfg.url);await page.waitForFunction('window.ready===true');
 const out=path.resolve(root,cfg.output);fs.mkdirSync(out,{recursive:true});const states=[];
 for(const sample of cfg.samples){const r=await page.evaluate(adapter.capture,sample,cfg);if(errors.length)throw Error(errors.join('\n'));const data=Buffer.from(r.image,'base64');if(data.subarray(1,4).toString()!=='PNG')throw Error('Reference must be PNG');fs.writeFileSync(path.join(out,sample.id+'.png'),data);states.push({sample,state:r.state});}
 fs.writeFileSync(path.join(out,'references.json'),JSON.stringify({config:cfg,states},null,2));console.log(JSON.stringify({output:out,count:states.length}));
}finally{await browser.close();}
