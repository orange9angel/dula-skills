// Absolute-time point sprites with explicit births, lifetimes and trajectories.
const frac=x=>x-Math.floor(x);
const random=(i,s)=>frac(Math.sin(i*127.1+s*311.7)*43758.5453);
const cache=new Map();
function sprite(color){
 if(cache.has(color))return cache.get(color);
 const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d');
 const r=g.createRadialGradient(32,32,0,32,32,32);r.addColorStop(0,'#fff8dc');r.addColorStop(.16,color);r.addColorStop(.5,color+'66');r.addColorStop(1,color+'00');g.fillStyle=r;g.fillRect(0,0,64,64);cache.set(color,c);return c;
}
export function emitStoryParticles(g,t,{start,end,count=36,life=2,seed=1,color='#ffd891',radius=3,alpha=.8,trajectory}){
 if(t<start||t>end+life)return 0;
 let visible=0;const image=sprite(color);g.save();g.globalCompositeOperation='lighter';
 for(let i=0;i<count;i++){
  const birth=start+(end-start)*i/Math.max(1,count-1),age=t-birth;
  if(age<0||age>=life)continue;
  const u=age/life,r=[random(i,seed),random(i,seed+1),random(i,seed+2)],p=trajectory(u,r,i,birth);
  if(!p)continue;
  const size=radius*(.6+r[1]*.8)*(1-u*.35);g.globalAlpha=alpha*Math.sin(Math.PI*u)**.55;
  g.drawImage(image,p[0]-size*2,p[1]-size*2,size*4,size*4);visible++;
 }
 g.restore();return visible;
}
