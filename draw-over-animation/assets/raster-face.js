// Authored raster identity with pixel-locked mouth cels and blink donors.
// Changes to expressive head pose remain in the shot, not a generic eye template.
export async function createRasterFacePainter(spec){
 const images=Object.fromEntries(await Promise.all(Object.entries(spec.images).map(async([key,src])=>{const im=new Image();im.src=src;await im.decode();return[key,im]})));
 const expressions=Object.fromEntries(await Promise.all(Object.entries(spec.expressions??{}).map(async([name,files])=>[name,Object.fromEntries(await Promise.all(Object.entries(files).map(async([key,src])=>{const im=new Image();im.src=src;await im.decode();return[key,im]})))])));
 const canvas=document.createElement('canvas');canvas.width=images.closed.width;canvas.height=images.closed.height;const g=canvas.getContext('2d');
 if(Object.values(images).some(im=>im.width!==canvas.width||im.height!==canvas.height))throw Error('Raster face cel dimensions differ');
 function paint({jaw=0,emotion='calm',blink=0,gaze=0,strain=0}={}){
  const state=jaw>.32?'open':jaw>.075?'half':'closed';g.clearRect(0,0,canvas.width,canvas.height);g.drawImage(images[state],0,0);
  if(strain>0&&expressions.strain){g.globalAlpha=Math.min(1,strain);g.drawImage(expressions.strain[state],0,0);g.globalAlpha=1;}
  if(blink>.60&&images.blink&&strain<.5)g.drawImage(images.blink,0,0);
  return{jaw,emotion,blink,gaze,strain,mouthCel:state,design:spec.id,identity:'authored raster',expressionScope:'authored mouth/blink and optional persistent expression donor'};
 }
 paint();return{canvas,paint,spec};
}
