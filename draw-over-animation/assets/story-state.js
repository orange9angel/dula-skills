// Persistent, seekable narrative state. Shot cuts never reset these tracks.
// Artwork declares what state it can depict; mismatches must be repaired in art.
export function createStoryState({cues,tracks}){
 const time=at=>typeof at==='number'?at:(()=>{if(!(at.cue in cues))throw Error('Unknown story cue '+at.cue);return cues[at.cue]+(at.offset??0);})();
 const resolved=Object.fromEntries(Object.entries(tracks).map(([id,keys])=>{
  const list=keys.map(k=>({...k,t:time(k.at)}));
  if(!list.length||list.some((k,i)=>!Number.isFinite(k.t)||(i&&k.t<=list[i-1].t)))throw Error('Invalid state track '+id);
  return[id,list];
 }));
 const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
 function at(t){
  const result={};
  for(const [id,keys] of Object.entries(resolved)){
   let i=0;while(i+1<keys.length&&keys[i+1].t<=t)i++;
   const k=keys[i],prev=keys[Math.max(0,i-1)];
   result[id]=k.duration&&typeof k.value==='number'?prev.value+(k.value-prev.value)*smooth((t-k.t)/k.duration):k.value;
  }return result;
 }
 return{at,tracks:resolved};
}
