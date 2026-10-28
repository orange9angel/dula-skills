// Eyelids close inside a fixed painted eye socket. Iris scale, nose, brow and
// facial silhouette never change; no generated face donor is pasted on blink.
const clamp=x=>Math.max(0,Math.min(1,x)),mix=(a,b,t)=>a+(b-a)*t;
export function blinkAmount(t,starts,{close=.065,hold=.025,open=.12}={}){
 for(const s of starts){const d=t-s;if(d<0||d>close+hold+open)continue;if(d<close){const u=d/close;return u*u*(3-2*u);}if(d<close+hold)return 1;const u=(d-close-hold)/open;return 1-u*u*(3-2*u);}return 0;
}
export function createFixedEyeRig(image,eyes){
 const sampleCanvas=document.createElement('canvas');sampleCanvas.width=image.naturalWidth;sampleCanvas.height=image.naturalHeight;const q=sampleCanvas.getContext('2d',{willReadFrequently:true});q.drawImage(image,0,0);
 const sample=([x,y])=>{const p=q.getImageData(Math.round(x),Math.round(y),1,1).data;return `rgb(${p[0]},${p[1]},${p[2]})`;};
 const specs=eyes.map(e=>({...e,skin:e.skinPoints.map(sample)}));
 return{draw(g,id,{blink=0}={}){let count=0;for(const e of specs.filter(e=>e.actor===id)){
  const [L,U1,U2,R,D1,D2]=e.curves,b=clamp(blink),C1=U1.map((v,i)=>mix(v,D2[i],.56)),C2=U2.map((v,i)=>mix(v,D1[i],.56));
  const a=U1.map((v,i)=>mix(v,C1[i],b)),c=U2.map((v,i)=>mix(v,C2[i],b)),d=D1.map((v,i)=>mix(v,C2[i],b)),f=D2.map((v,i)=>mix(v,C1[i],b));
  const bound=()=>{g.beginPath();g.moveTo(...L);g.bezierCurveTo(...U1,...U2,...R);g.bezierCurveTo(...D1,...D2,...L);g.closePath();};
  if(b<=.00001){count++;continue;}
  g.save();const clip=e.bounds??[Math.min(L[0],R[0])-1,Math.min(U1[1],U2[1])-1,Math.abs(R[0]-L[0])+2,Math.max(D1[1],D2[1])-Math.min(U1[1],U2[1])+3];g.beginPath();g.rect(...clip);g.clip();
  const fill=g.createLinearGradient(0,U1[1]-2,0,Math.max(D1[1],D2[1])+2);fill.addColorStop(0,e.skin[0]);fill.addColorStop(1,e.skin[1]);g.fillStyle=fill;
  bound();g.fill();g.strokeStyle=fill;g.lineWidth=2;g.stroke();
  // Re-expose the original iris through an aperture; the iris is neither
  // translated nor squeezed. Both lids meet at the same closed curve.
  if(b<.9999){g.save();g.beginPath();g.moveTo(...L);g.bezierCurveTo(...a,...c,...R);g.bezierCurveTo(...d,...f,...L);g.closePath();g.clip();g.drawImage(image,0,0);g.restore();}
  g.strokeStyle=e.ink;g.lineWidth=e.lineWidth??.9;g.lineCap='round';g.beginPath();g.moveTo(...L);g.bezierCurveTo(...a,...c,...R);g.stroke();g.restore();count++;
 }return count;},specs};
}
