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

// Inspect independent dimensions across a complete ordered trace, including cuts.
// A missing component is a failure unless the caller explicitly selects visible
// samples. Hidden armor is not evidence of an intact or damaged visible surface.
export function checkContinuityTraces({samples,rules}){
 const get=(x,key)=>key.split('.').reduce((v,k)=>v?.[k],x),checks=[];
 for(const rule of rules){
  const selected=samples.filter(s=>(rule.start===undefined||s.t>=rule.start)&&(rule.end===undefined||s.t<rule.end));
  if(selected.length<2){checks.push({id:rule.id,passed:false,reason:'Insufficient trace samples'});continue;}
  let previous=null;
  for(const s of selected){const value=get(s,rule.field);let passed=value!==undefined&&value!==null,reason=passed?'':'Missing field';
   if(previous&&passed){
    if(rule.nondecreasing&&!(typeof value==='number'&&value>=previous.value)){passed=false;reason='State regressed';}
    if(rule.maxStep!==undefined&&!(typeof value==='number'&&Math.abs(value-previous.value)<=rule.maxStep)){passed=false;reason='Step exceeded';}
    if(rule.transitions&&value!==previous.value&&!rule.transitions.some(p=>p[0]===previous.value&&p[1]===value)){passed=false;reason='Undeclared transition';}
   }
   checks.push({id:rule.id,t:s.t,previous:previous?.value??null,value:value??null,passed,reason});
   previous={value};
  }
 }
 return{passed:checks.every(c=>c.passed),checks,note:'Trace consistency only; artwork and semantic performance require separate visible evidence.'};
}
