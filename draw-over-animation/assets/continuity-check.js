// Contract checking only: visible frames still require narrative/visual review.
export async function checkStoryContracts({sample,contracts,cues}){
 const time=x=>{const t=typeof x==='number'?x:cues[x.cue]+(x.offset??0);if(!Number.isFinite(t))throw Error('Unresolved contract time '+JSON.stringify(x));return t;};
 const get=(x,key)=>key.split('.').reduce((v,k)=>v?.[k],x);
 const checks=[];
 for(const c of contracts){
  for(const at of c.at){const t=time(at),state=await sample(t);for(const [field,expect] of Object.entries(c.expect)){
   const actual=get(state,field),pass=('equals' in expect?actual===expect.equals:true)&&('oneOf' in expect?expect.oneOf.includes(actual):true)&&('min' in expect?typeof actual==='number'&&actual>=expect.min:true)&&('max' in expect?typeof actual==='number'&&actual<=expect.max:true);
   checks.push({id:c.id,t,field,actual:actual??null,expect,passed:pass});
  }}
 }return{passed:checks.every(c=>c.passed),checks,note:'Runtime story contracts do not certify artwork, visibility, or natural acting.'};
}
