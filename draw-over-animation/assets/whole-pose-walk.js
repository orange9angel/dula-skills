// Whole-cel pose selection from an actual 3D bake. No detached leg layers.
// Authored foot/pelvis landmarks belong to each cel; only small continuous
// registration corrections are interpolated across the intact drawing mesh.
export function chooseWholePose(actor,candidates){
 const vector=a=>['leftFoot','rightFoot'].flatMap(k=>[a.world[k][0]-a.root[0],(a.world[k][1]-.09)*2]).concat([(a.world.pelvis[1]-1)*1.5]);
 const v=vector(actor);let best=null,error=Infinity;
 for(const c of candidates){const w=vector(c.reference),d=v.reduce((s,x,i)=>s+(x-w[i])**2,0);if(d<error){error=d;best=c;}}
 return{pose:best,error};
}
export function makeWholePoseWarp({width,height,anchors,radius=180}){
 const basis=(a,b)=>Math.exp(-((a[0]-b[0])**2+(a[1]-b[1])**2)/(radius*radius));
 const n=anchors.length,m=anchors.map((a,i)=>anchors.map((b,j)=>basis(a.source,b.source)+(i===j?.00001:0)).concat([a.target[0]-a.source[0],a.target[1]-a.source[1]]));
 for(let i=0;i<n;i++){let pivot=i;for(let j=i+1;j<n;j++)if(Math.abs(m[j][i])>Math.abs(m[pivot][i]))pivot=j;[m[i],m[pivot]]=[m[pivot],m[i]];const d=m[i][i];if(Math.abs(d)<1e-8)throw Error('Degenerate whole-cel anchors');for(let j=i;j<n+2;j++)m[i][j]/=d;for(let k=0;k<n;k++){if(k===i)continue;const f=m[k][i];for(let j=i;j<n+2;j++)m[k][j]-=f*m[i][j];}}
 return(u,v)=>{const p=[(u-.5)*width,(v-1)*height];let dx=0,dy=0;for(let i=0;i<n;i++){const w=basis(p,anchors[i].source);dx+=w*m[i][n];dy+=w*m[i][n+1];}return[dx,dy];};
}
