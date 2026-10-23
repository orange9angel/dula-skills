// Camera-specific two-bone drawing deformation. Bind landmarks are authored
// in the cel, targets in display pixels. A planted boot has a separate rigid
// translation so calf rotation does not turn its sole into a sliding point.
const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]],add=(a,b)=>[a[0]+b[0],a[1]+b[1]],length=a=>Math.hypot(...a);
function knee(h,f,a,b,bend){const d0=sub(f,h),d=Math.min(length(d0),a+b-.001),u=d0.map(v=>v/(length(d0)||1)),along=(a*a-b*b+d*d)/(2*d),cross=Math.sqrt(Math.max(0,a*a-along*along));return[h[0]+u[0]*along-u[1]*cross*bend,h[1]+u[1]*along+u[0]*cross*bend];}
function turn(point,pivot,targetPivot,sourceEnd,targetEnd){const a=sub(sourceEnd,pivot),b=sub(targetEnd,targetPivot),r=Math.atan2(b[1],b[0])-Math.atan2(a[1],a[0]),p=sub(point,pivot),c=Math.cos(r),s=Math.sin(r);return[targetPivot[0]+p[0]*c-p[1]*s,targetPivot[1]+p[0]*s+p[1]*c];}
function distance(p,a,b){const d=sub(b,a),v=sub(p,a),q=clamp((v[0]*d[0]+v[1]*d[1])/(d[0]*d[0]+d[1]*d[1]));return length(sub(p,[a[0]+q*d[0],a[1]+q*d[1]]));}
export function makeLegDeformer({width,height,legs,targets,hipGate=.50,legIndex=null}){
 const point=p=>[(p[0]-.5)*width,(p[1]-1)*height];
 const rigs=legs.map((l,i)=>{const h=point(l.hip),k=point(l.knee),f=point(l.ankle),target=targets[i];return{h,k,f,target,solved:knee(h,target,length(sub(k,h)),length(sub(f,k)),l.bend??1),definition:l};});
 const deform=(u,v)=>{
  if(v<hipGate-.03)return[0,0];const p=point([u,v]);
  const distances=rigs.map(r=>Math.min(distance(p,r.h,r.k),distance(p,r.k,r.f))),index=legIndex??(distances[0]<=distances[1]?0:1),r=rigs[index];
  const thigh=turn(p,r.h,r.h,r.k,r.solved),calf=turn(p,r.k,r.solved,r.f,r.target),boot=add(p,sub(r.target,r.f));
  const kWeight=smooth((v-r.definition.knee[1]+.045)/.09),bootWeight=smooth((v-r.definition.ankle[1]+.10)/.09),gate=smooth((v-hipGate+.03)/.07);
  const q=thigh.map((n,i)=>n+(calf[i]-n)*kWeight),q2=q.map((n,i)=>n+(boot[i]-n)*bootWeight);
  return[(q2[0]-p[0])*gate,(q2[1]-p[1])*gate];
 };deform.joints=rigs[legIndex??0];return deform;
}
export function plantedWalk({time,startX,velocity,ground=0,cycle=3,stance=.60,lift=18,lead=25}){
 const direction=Math.sign(velocity)||1;
 return[0,cycle/2].map(offset=>{const phaseTime=time+offset,k=Math.floor(phaseTime/cycle),age=phaseTime-k*cycle,plant=startX+velocity*(k*cycle-offset)+direction*lead;
  const q=clamp((age/cycle-stance)/(1-stance)),x=plant+velocity*cycle*smooth(q),y=ground-lift*Math.sin(Math.PI*q);
  return{x,y,contact:q===0||q===1};
 });
}
