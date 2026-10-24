// Reuse reviewed RGBA frames without adding another deformation to the head/body.
// Coordinates and cycle travel are authored per actor/view; not a foot-lock solver.
export async function createBakedCelClip({stage,spec}){
 const images=await Promise.all(spec.frames.map(async src=>{const im=new Image();im.src=src;await im.decode();return im;}));
 if(!images.length||images.some(im=>im.width!==spec.size[0]||im.height!==spec.size[1]))throw Error('Baked clip dimensions differ');
 const canvas=document.createElement('canvas');[canvas.width,canvas.height]=spec.size;const g=canvas.getContext('2d');
 stage.register(spec.id,canvas,{dynamic:true});let cached=-1;
 function place({distance=0,direction=1,x,y,height,view,order=2,phaseOffset=0}){
  const phase=direction*distance/spec.cycleTravel+phaseOffset,index=((Math.floor(phase*images.length)%images.length)+images.length)%images.length;
  if(index!==cached){g.clearRect(0,0,canvas.width,canvas.height);g.drawImage(images[index],0,0);cached=index;}
  const s=height/canvas.height,px=x+(canvas.width/2-spec.anchor[0])*s,py=y+(canvas.height-spec.anchor[1])*s;
  stage.place(spec.id,{x:px,y:py,height,view,order,time:0,breath:0,hair:0,motion:[0,0]});
  const landmarks=spec.landmarks?.[index]??{};
  const point=p=>[x+(p[0]-spec.anchor[0])*s,y+(p[1]-spec.anchor[1])*s];
  return{key:spec.id,index,phase,wholeCel:true,baked:true,distance,direction,x,y,height,feet:(landmarks.feet??[]).map(p=>({x:point(p)[0],y:point(p)[1]})),cuff:point(landmarks.cuff??spec.cuff),sourceImage:spec.frames[index]};
 }
 return{place,canvas,spec};
}
