// Locked-variant raster face: a base portrait plus pixel-locked variant windows
// (image-lipsync lock-in craft: every variant is pixel-identical to the base
// outside its own rect). Mouth states are categorical cels — no cross-dissolve
// of ink contours. Because variants share the same base画形, stacking a mouth
// window onto an expression layer never introduces the跨图移植 seam; the only
// known limit is that a mouth variant carries the base mouth's expression.
//
// spec = {
//   id, base: src,
//   variants: {key: {src, rect:[x,y,w,h]}},   // rects in base image pixels
//   mouth: {half: key, open: key},            // jaw 三态 -> variant key
//   blink: key,                               // blink donor window
//   emotions: {emotionName: variantKey|null}, // shot emotion -> expression layer (null=base)
// }
export async function createLockedVariantFace(spec){
  const load=async src=>{const im=new Image();im.src=src;await im.decode();return im;};
  const base=await load(spec.base);
  const variants={};
  for(const [k,v] of Object.entries(spec.variants??{}))variants[k]={image:await load(v.src),rect:v.rect};
  for(const [k,v] of Object.entries(variants))
    if(v.image.width!==base.width||v.image.height!==base.height)
      throw Error(`Locked variant ${k} dimensions differ from base (${spec.id})`);
  const canvas=document.createElement('canvas');canvas.width=base.width;canvas.height=base.height;
  const g=canvas.getContext('2d');
  const paste=key=>{const v=variants[key];if(!v)return;const [x,y,w,h]=v.rect;g.drawImage(v.image,x,y,w,h,x,y,w,h);};
  function paint({jaw=0,emotion=null,blink=0}={}){
    const expressionCel=emotion!=null?(spec.emotions?.[emotion]??null):null;
    const mouthCel=jaw>.32?'open':jaw>.075?'half':'closed';
    g.clearRect(0,0,canvas.width,canvas.height);
    g.drawImage(expressionCel?variants[expressionCel].image:base,0,0);
    if(mouthCel!=='closed'&&spec.mouth?.[mouthCel])paste(spec.mouth[mouthCel]);
    if(blink>.60&&spec.blink)paste(spec.blink);
    return{jaw,emotion,blink,mouthCel,expressionCel:expressionCel??'base',
      identity:'locked variant raster',design:spec.id};
  }
  paint();
  return{canvas,paint,spec};
}
