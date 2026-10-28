// Same-image local animation. Feature islands carry their own soft masks;
// expression changes cannot replace an unrelated full portrait/background.
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
export async function createFeatheredVariantFace(spec){
 const load=async src=>{const im=new Image();im.src=src;await im.decode();return im;};
 const base=await load(spec.base), canvas=document.createElement('canvas');
 canvas.width=base.width;canvas.height=base.height;
 const g=canvas.getContext('2d'), patches={};
 for(const [key,v] of Object.entries(spec.variants??{})){
  const im=await load(v.src);
  if(!v.sourceRect&&(im.width!==base.width||im.height!==base.height))throw Error(`Variant size drift: ${spec.id}/${key}`);
  const [x,y,w,h]=v.rect, c=document.createElement('canvas');c.width=w;c.height=h;
  const q=c.getContext('2d',{willReadFrequently:true});
  const sr=v.sourceRect??[x,y,w,h],sx=im.width/(v.sourceSize?.[0]??im.width),sy=im.height/(v.sourceSize?.[1]??im.height);
  q.drawImage(im,sr[0]*sx,sr[1]*sy,sr[2]*sx,sr[3]*sy,0,0,w,h);
  const d=q.getImageData(0,0,w,h), islands=v.islands??[[x+w/2,y+h/2,w/2,h/2]],f=v.feather??.24;
  for(let py=0;py<h;py++)for(let px=0;px<w;px++){
   let a=0;
   if(v.cores){
    // Opaque feature union, feather only outside it. Smile corners and raised
    // eyelids must not survive underneath the falloff of a smaller new shape.
    for(const [cx,cy,cw,ch,pad] of v.cores){
     const dx=Math.max(cx-(px+x),0,px+x-(cx+cw)),dy=Math.max(cy-(py+y),0,py+y-(cy+ch));
     a=Math.max(a,smooth(1-Math.hypot(dx,dy)/pad));
    }
   }else for(const [cx,cy,rx,ry] of islands){const r=Math.hypot((px+x-cx)/rx,(py+y-cy)/ry);a=Math.max(a,smooth((1-r)/f));}
   d.data[(py*w+px)*4+3]*=a*smooth(Math.min(px,py,w-1-px,h-1-py)/2);
  }
  q.putImageData(d,0,0);patches[key]={canvas:c,x,y};
 }
 function paste(key,alpha=1){const p=patches[key];if(p){g.globalAlpha=alpha;g.drawImage(p.canvas,p.x,p.y);g.globalAlpha=1;}}
 function paint({jaw=0,emotion=null,blink=0,layers=[]}={}){
  const expressionCel=spec.emotions?.[emotion]??null,mouthCel=jaw>.32?'open':jaw>.075?'half':'closed';
  g.clearRect(0,0,canvas.width,canvas.height);g.drawImage(base,0,0);
  if(expressionCel)paste(expressionCel);
  for(const key of layers)paste(key);
  if(mouthCel!=='closed'||spec.mouth?.closed)paste(spec.mouth?.[mouthCel]);
  const bank=spec.blinkByExpression?.[expressionCel]??spec.blink;
  const blinkCel=typeof bank==='object'?(blink>.80?bank.closed:blink>.18?bank.half:null):(blink>.52?bank:null);
  if(blinkCel)paste(blinkCel);
  return{jaw,emotion,blink,mouthCel,blinkCel,expressionCel:expressionCel??'base'};
 }
 paint();return{canvas,paint,spec,patches};
}
