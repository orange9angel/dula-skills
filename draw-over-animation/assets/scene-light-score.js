// Deterministic light state shared by scene and character receivers.
// Painted consumers need registered receiver masks/normals/occlusion; this
// evaluator alone does not make an independently painted plate physically lit.
export function createSceneLightScore({cues,lights}){
 const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
 const lerp=(a,b,u)=>Array.isArray(b)?b.map((v,i)=>a[i]+(v-a[i])*u):typeof b==='number'?a+(b-a)*u:(u<1?a:b);
 const tracks=Object.fromEntries(Object.entries(lights).map(([id,keys])=>[id,keys.map(k=>{
  const base=k.at.cue?cues[k.at.cue]:0;if(!Number.isFinite(base))throw Error('Unknown light cue '+k.at.cue);
  return {...k,t:base+(k.at.offset??0)};
 }).map((k,i,a)=>{if(i&&k.t<=a[i-1].t)throw Error('Unordered light keys '+id);return k;})]));
 function at(t){const out={};for(const [id,keys] of Object.entries(tracks)){
  let i=0;while(i+1<keys.length&&keys[i+1].t<=t)i++;
  const k=keys[i],prev=keys[Math.max(0,i-1)],u=k.duration?smooth((t-k.t)/k.duration):1;
  out[id]=Object.fromEntries(Object.entries(k.value).map(([name,value])=>[name,lerp(prev.value[name]??value,value,u)]));
 }return out;}
 return {at,tracks};
}
