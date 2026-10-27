// All painted geometry, actors and their contact/effect anchors share one camera.
// Coordinates are in the native plate pixels; screen inserts are explicit exceptions.
export const saturate=x=>Math.max(0,Math.min(1,x));
export const lerp=(a,b,t)=>a+(b-a)*t;
export function travelProgress(t,start,end,ramp=.12){
  const u=saturate((t-start)/(end-start)),k=1/(1-ramp);
  if(u<ramp)return k*u*u/(2*ramp);
  if(u>1-ramp)return 1-k*(1-u)*(1-u)/(2*ramp);
  return k*(u-ramp/2);
}
export function paintedCamera(spec,t,start,end,width=1280,height=720){
  const q=saturate((t-start)/(end-start));
  const a=spec?.from??[960,540,1],b=spec?.to??a;
  const z=Math.max(1,lerp(a[2],b[2],q)),scale=Math.max(width/1920,height/1080)*z;
  // A plate has finite extent. Clamp the camera itself so every actor, contact
  // and practical-light anchor inherits the same correction.
  const cx=Math.max(width-1920*scale,Math.min(0,width/2-lerp(a[0],b[0],q)*scale));
  const cy=Math.max(height-1080*scale,Math.min(0,height/2-lerp(a[1],b[1],q)*scale));
  return{scale,x:cx,y:cy,z,point:p=>[cx+p[0]*scale,cy+p[1]*scale],
    inverse:p=>[(p[0]-cx)/scale,(p[1]-cy)/scale]};
}
export function pathPoint(spec,t,start,end){
  const u=spec.walk?travelProgress(t,spec.walk.start??start,spec.walk.end??end):saturate((t-start)/(end-start));
  const knots=spec.path??[spec.at,spec.to??spec.at];
  const at=Math.min(knots.length-2,Math.floor(u*(knots.length-1))),q=u*(knots.length-1)-at;
  return{position:knots[at].map((v,i)=>lerp(v,knots[at+1][i],q)),u};
}
export function actorInPlate(spec,t,start,end,camera){
  const {position:p,u}=pathPoint(spec,t,start,end),xy=spec.screen?p:camera.point(p);
  const h=p[2]*(spec.screen?1:camera.scale);
  const phase=spec.walk?u*(spec.walk.steps??8)/2:0;
  return{x:xy[0],y:xy[1],h,u,phase,index:Math.floor(phase*8)%8,
    planted:Math.floor(phase*2)%2?'right':'left',plate:p};
}
export function contactSchedule(spec,start,end){
  if(!spec.walk)return[];
  const n=spec.walk.steps??8,out=[];
  for(let k=1;k<=n;k++){
    let lo=spec.walk.start??start,hi=spec.walk.end??end;
    for(let j=0;j<35;j++){const m=(lo+hi)/2;if(travelProgress(m,spec.walk.start??start,spec.walk.end??end)<k/n)lo=m;else hi=m;}
    out.push({time:(lo+hi)/2,side:k%2?'right':'left',step:k});
  }
  return out;
}
export function softContact(g,x,y,h,{opacity=.3,cast=[20,5]}={}){
  const rx=Math.max(2,h*.075),ry=Math.max(1,h*.016);
  g.save();g.translate(x,y);g.scale(rx,ry);
  const q=g.createRadialGradient(0,0,0,0,0,1.8);q.addColorStop(0,`rgba(7,12,25,${opacity})`);q.addColorStop(1,'rgba(7,12,25,0)');
  g.fillStyle=q;g.fillRect(-1.8,-1.8,3.6,3.6);g.restore();
  g.save();g.translate(x+cast[0]*h/400,y+cast[1]*h/400);g.rotate(.18);g.scale(rx*2.4,ry*1.3);
  const r=g.createRadialGradient(0,0,0,0,0,1);r.addColorStop(0,`rgba(8,16,32,${opacity*.35})`);r.addColorStop(1,'rgba(8,16,32,0)');g.fillStyle=r;g.fillRect(-1,-1,2,2);g.restore();
}
