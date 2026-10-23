// Generated browser runtime owned by draw-over-animation. No episode imports.
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*(3-2*x);};
const mix=(a,b,u)=>a+(b-a)*u;
const gauss=(x,y,cx,cy,rx,ry)=>Math.exp(-(((x-cx)/rx)**2+((y-cy)/ry)**2)*2);

export function createMotionController({motion,poseEdits={curves:[]},rigs,pixelsPerMeter=180,maxDelta=38,pinRadius=[90,80]}){
 if(!motion.frames?.length||!(motion.fps>0))throw Error('Empty motion bake or invalid fps');
 let offsets={};
 function frameAt(t){return motion.frames[Math.max(0,Math.min(motion.frames.length-1,Math.round((t-motion.start)*motion.fps)))];}
 function update(t){
  const frame=frameAt(t),f=(t-motion.start)*motion.fps;offsets={};
  for(const [key,rig]of Object.entries(rigs)){
   const a=frame.actors[rig.actor],b=motion.frames[rig.ref]?.actors[rig.actor];
   if(!a||!b)throw Error(`Missing actor/reference frame for ${key}`);offsets[key]={};
   for(const joint of Object.keys(rig.j)){
    const p=a.world[joint],q=b.world[joint];if(!p||!q)throw Error(`Missing ${rig.actor}.${joint}`);
    let dx=((p[0]-a.root[0])-(q[0]-b.root[0]))*pixelsPerMeter,dy=-((p[1]-a.root[1])-(q[1]-b.root[1]))*pixelsPerMeter;
    dx=Math.max(-maxDelta,Math.min(maxDelta,dx));dy=Math.max(-maxDelta,Math.min(maxDelta,dy));
    for(const c of poseEdits.curves.filter(c=>c.cel===key&&c.joint===joint)){
     if(c.keys.length<2)throw Error(`Curve needs at least two keys: ${key}.${joint}`);
     if(f<c.keys[0][0]||f>c.keys.at(-1)[0])continue;
     const i=Math.min(c.keys.length-2,c.keys.findLastIndex(k=>k[0]<=f)),p=c.keys[i],q=c.keys[i+1];
     if(q[0]<=p[0])throw Error('Curve frame keys must increase');
     const u=ease((f-p[0])/(q[0]-p[0]));dx+=mix(p[1],q[1],u);dy+=mix(p[2],q[2],u);
    }
    if(!Number.isFinite(dx)||!Number.isFinite(dy))throw Error(`Non-finite motion offset: ${key}.${joint}`);
    offsets[key][joint]=[dx,dy];
   }
  }
  return frame.frame;
 }
 function deform(key,x,y,dx=0,dy=0){
  const rig=rigs[key];if(rig){let px=0,py=0,total=1;
   for(const [joint,p]of Object.entries(rig.j)){const w=gauss(x,y,...p),d=offsets[key]?.[joint];if(!d)throw Error('Call update(t) before deform()');px+=d[0]*w;py+=d[1]*w;total+=w;}
   let free=1;for(const p of rig.pins??[])free*=1-gauss(x,y,p[0],p[1],...pinRadius);
   dx=(dx+px/total)*free;dy=(dy+py/total)*free;
  }
  return[x+dx,y+dy];
 }
 return{frameAt,update,deform,get offsets(){return offsets;}};
}
