// Same-source parts: rigid hands/props; bone-axis foreshortening for limb segments.
// Fixed-view projection only, without optical flow or incompatible-cel morphing.
const pathFor=(g,p)=>{g.beginPath();p.forEach(([x,y],i)=>i?g.lineTo(x,y):g.moveTo(x,y));g.closePath();};
export const easeRig=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(x*(x*6-15)+10);};
export function createPaintedPart(image,{polygon,pivot,padding=0,maskImage=null}){
 const x=Math.floor(Math.min(...polygon.map(p=>p[0]))-3),y=Math.floor(Math.min(...polygon.map(p=>p[1]))-3),w=Math.ceil(Math.max(...polygon.map(p=>p[0]))-x+3),h=Math.ceil(Math.max(...polygon.map(p=>p[1]))-y+3);
 const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const g=canvas.getContext('2d');
 g.translate(-x,-y);pathFor(g,polygon);g.fillStyle='#fff';g.fill();if(padding){g.lineWidth=padding*2;g.lineJoin='round';g.strokeStyle='#fff';g.stroke();}
 g.globalCompositeOperation='source-in';g.drawImage(image,0,0);if(maskImage){g.globalCompositeOperation='destination-in';g.drawImage(maskImage,0,0);}g.resetTransform();g.globalCompositeOperation='source-over';
 const shadow=document.createElement('canvas');shadow.width=w;shadow.height=h;const sg=shadow.getContext('2d');sg.drawImage(canvas,0,0);sg.globalCompositeOperation='source-in';sg.fillStyle='#241624';sg.fillRect(0,0,w,h);
 function draw(ctx,{at=pivot,angle=0,alpha=1,shadowOnly=false}={}){ctx.save();ctx.globalAlpha*=alpha;ctx.translate(...at);ctx.rotate(angle);ctx.drawImage(shadowOnly?shadow:canvas,x-pivot[0],y-pivot[1]);ctx.restore();}
 function point(p,{at=pivot,angle=0}={}){const c=Math.cos(angle),s=Math.sin(angle),dx=p[0]-pivot[0],dy=p[1]-pivot[1];return[at[0]+c*dx-s*dy,at[1]+s*dx+c*dy];}
 function drawBone(ctx,sourceEnd,targetStart,targetEnd){const originalAngle=Math.atan2(sourceEnd[1]-pivot[1],sourceEnd[0]-pivot[0]),targetAngle=Math.atan2(targetEnd[1]-targetStart[1],targetEnd[0]-targetStart[0]),scale=Math.hypot(targetEnd[0]-targetStart[0],targetEnd[1]-targetStart[1])/Math.hypot(sourceEnd[0]-pivot[0],sourceEnd[1]-pivot[1]);ctx.save();ctx.translate(targetStart[0],targetStart[1]);ctx.rotate(targetAngle);ctx.scale(scale,1);ctx.rotate(-originalAngle);ctx.drawImage(canvas,x-pivot[0],y-pivot[1]);ctx.restore();return scale;}
 return {canvas,draw,drawBone,point,pivot,polygon};
}
export function createCleanUnderlay(image,polygons,{padding=2,maskImage=null}={}){
 const canvas=document.createElement('canvas');canvas.width=image.naturalWidth??image.width;canvas.height=image.naturalHeight??image.height;const g=canvas.getContext('2d');g.fillStyle=g.strokeStyle='#fff';g.lineJoin='round';g.lineWidth=padding*2;
 if(maskImage)g.drawImage(maskImage,0,0);else for(const p of polygons){pathFor(g,p);g.fill();g.stroke();}g.globalCompositeOperation='source-in';g.drawImage(image,0,0);return canvas;
}
export function solveSpatialPaintedArm(shoulder,elbow,wrist,target,depth=0){
 const a=Math.hypot(elbow[0]-shoulder[0],elbow[1]-shoulder[1]),b=Math.hypot(wrist[0]-elbow[0],wrist[1]-elbow[1]);
 const delta=[target[0]-shoulder[0],target[1]-shoulder[1],0],raw=Math.hypot(...delta),d=Math.max(Math.abs(a-b)+.001,Math.min(a+b-.001,raw)),axis=delta.map(x=>x/raw);
 const pole=[0,1,depth],dot=pole.reduce((s,v,i)=>s+v*axis[i],0),normal=pole.map((v,i)=>v-dot*axis[i]),len=Math.hypot(...normal);normal.forEach((v,i)=>normal[i]=v/Math.max(1e-6,len));
 const u=(a*a-b*b+d*d)/(2*d),h=Math.sqrt(Math.max(0,a*a-u*u)),e=[0,1,2].map(i=>(shoulder[i]??0)+axis[i]*u+normal[i]*h),w=[0,1,2].map(i=>(shoulder[i]??0)+axis[i]*d);
 return{elbow:e,wrist:w,angle:Math.atan2(w[1]-e[1],w[0]-e[0])-Math.atan2(wrist[1]-elbow[1],wrist[0]-elbow[0]),boneLengths:[a,b],reach:raw/(a+b)};
}
