// Character-authored facial curves. This renderer does not invent a face:
// landmarks, eye/brow design, lip profile and occlusion belong to the artwork.
const clamp=x=>Math.max(0,Math.min(1,x));
function curve(g,p,close=false){g.beginPath();g.moveTo(...p[0]);for(let i=1;i<p.length;i++){const v=p[i];if(v.length===6)g.bezierCurveTo(...v);else if(v.length===4)g.quadraticCurveTo(...v);else g.lineTo(...v);}if(close)g.closePath();}
function fill(g,p,color){curve(g,p,true);g.fillStyle=color;g.fill();}
function stroke(g,p,color,width){curve(g,p);g.strokeStyle=color;g.lineWidth=width;g.stroke();}
export function createAuthoredFacePainter(image,spec){
 const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
 const g=canvas.getContext('2d'),layer=document.createElement('canvas');layer.width=canvas.width;layer.height=canvas.height;
 const c=layer.getContext('2d'),unit=canvas.width/(spec.designSize??1254);
 // Source skin is an occlusion matte: brows/eyes cannot paint over a fringe,
 // the nose silhouette or empty pixels. The authored ROI excludes costume.
 const mask=document.createElement('canvas');mask.width=canvas.width;mask.height=canvas.height;const m=mask.getContext('2d',{willReadFrequently:true});m.drawImage(image,0,0);
 const pixels=m.getImageData(0,0,mask.width,mask.height),roi=spec.skinROI;
 for(let y=0;y<mask.height;y++)for(let x=0;x<mask.width;x++){const i=(y*mask.width+x)*4,[r,gg,b,a]=pixels.data.slice(i,i+4);const visible=x/unit>roi[0]&&x/unit<roi[2]&&y/unit>roi[1]&&y/unit<roi[3]&&r>150&&r>gg*1.04&&gg>b*1.03;pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=255;pixels.data[i+3]=visible?a:0;}m.putImageData(pixels,0,0);
 function paint({jaw=0,emotion='calm',blink=0,gaze=0,intensity=1}={}){
  const tense=['cold','threat','resolve','defiant','shout'].includes(emotion),pain=emotion==='pain',sad=['sad','tired_smile'].includes(emotion),surprised=['surprise','wonder'].includes(emotion),smile=['wry','relief','tired_smile'].includes(emotion);
  c.clearRect(0,0,layer.width,layer.height);c.save();c.scale(unit,unit);c.lineCap='round';c.lineJoin='round';
  for(const eye of spec.eyes){
   const [a,b]=[eye.inner,eye.outer],dx=b[0]-a[0],dy=b[1]-a[1],w=Math.hypot(dx,dy),side=Math.sign(dx),angle=Math.atan2(dy,dx),open=(1-clamp(blink))*(pain?.48:sad?.68:surprised?1.23:tense?.91:1);
   c.save();c.translate(...a);c.rotate(angle);c.scale(1,side);
   const top=(eye.upper??.15)*w*open,low=(eye.lower??.21)*w*open,arch=eye.arch??.5;
   const upper=[[0,0],[w*.20,-top*.16,w*arch,-top,w,0]],lower=[[w,0],[w*.73,low*.90,w*.28,low*1.13,0,0]];
   if(open>.055){
    curve(c,[...upper,...lower.slice(1)],true);c.fillStyle='#fff2dc';c.fill();c.save();c.clip();
    const ix=w*clamp((eye.irisAt??.48)+gaze*.10),iy=low*.22,rx=w*(eye.irisWidth??.16),ry=w*(eye.irisHeight??.245);
    c.fillStyle=spec.iris.dark;c.beginPath();c.ellipse(ix,iy,rx,ry,0,0,Math.PI*2);c.fill();
    const col=c.createLinearGradient(0,-ry,0,ry);col.addColorStop(0,spec.iris.dark);col.addColorStop(.50,spec.iris.mid);col.addColorStop(1,spec.iris.light);
    c.fillStyle=col;c.beginPath();c.ellipse(ix,iy+ry*.05,rx*.82,ry*.87,0,0,Math.PI*2);c.fill();
    c.fillStyle=spec.ink;c.beginPath();c.ellipse(ix,iy-ry*.08,rx*.32,ry*.70,0,0,Math.PI*2);c.fill();
    stroke(c,[[ix-rx*.55,iy+ry*.50],[ix,iy+ry*.75,ix+rx*.60,iy+ry*.44]],spec.iris.light,w*.013);
    c.fillStyle='#fff9e8';c.beginPath();c.ellipse(ix-rx*.27,iy-ry*.47,rx*.22,ry*.17,-.2,0,Math.PI*2);c.fill();
    fill(c,[[0,0],[w*.2,-top*.16,w*arch,-top,w,0],[w*.75,6,w*.3,6,0,3]],'rgba(56,34,48,.16)');
    c.restore();
    // Tapered upper lash: a filled ribbon, not a uniform outlined almond.
    fill(c,[...upper,[w*.77,-top*.32-w*.035,w*.25,-top*.22-w*.018,0,-w*.006]],spec.ink);
    stroke(c,upper,spec.ink,w*.025);
    stroke(c,lower,spec.ink,w*.012);
    stroke(c,[[w*.94,0],[w*1.025,-w*.025]],spec.ink,w*.018);
   }else stroke(c,[[0,0],[w*.35,w*.09,w*.72,w*.05,w,0]],spec.ink,w*.026);
   const browRaise=surprised?-w*.10:sad?-w*.04:pain?w*.016:0,browInner=(tense?w*.014:sad?-w*.07:0),by=-w*(eye.browGap??.19)+browRaise;
   fill(c,[[-w*.025,by+browInner],[w*.24,by-w*.04,w*.65,by-w*.085,w*1.02,by-w*.065],[w*.72,by-w*.025,w*.24,by+w*.025,-w*.025,by+w*.024+browInner]],spec.brow??spec.ink);
   stroke(c,[[w*.12,-top-w*.052],[w*.45,-top-w*.085,w*.83,-top-w*.045]],spec.crease??'#a57867',w*.009);
   if(pain)stroke(c,[[w*.24,low+w*.07],[w*.45,low+w*.1,w*.66,low+w*.06]],'#aa7969',w*.01);
   c.restore();
  }
  const a=spec.mouth.inner,b=spec.mouth.outer,dx=b[0]-a[0],dy=b[1]-a[1],w=Math.hypot(dx,dy),side=Math.sign(dx);
  c.save();c.translate(...a);c.rotate(Math.atan2(dy,dx));c.scale(1,side);
  const opening=clamp(jaw)*(emotion==='shout'?.56:.31)*w,lip=smile?.075:pain?-.015:.012;
  if(opening>w*.025){
   const shape=[[0,0],[w*.28,-w*.025,w*.68,-w*.015,w,0],[w*.84,opening*.84,w*.36,opening*1.13,0,0]];
   fill(c,shape,'#58363c');c.save();curve(c,shape,true);c.clip();
   fill(c,[[0,0],[w*.28,-w*.025,w*.68,-w*.015,w,0],[w*.82,w*.055,w*.3,w*.065,0,w*.018]],'#fff0da');
   if(opening>w*.16)fill(c,[[w*.25,opening*.84],[w*.48,opening*.47,w*.78,opening*.65,w*.86,opening],[w*.2,opening]],'#ae7076');c.restore();
   stroke(c,[[0,0],[w*.28,-w*.025,w*.68,-w*.015,w,0]],spec.ink,w*.021);
   stroke(c,[[w,0],[w*.84,opening*.84,w*.36,opening*1.13,0,0]],'#88594f',w*.014);
  }else if(pain||emotion==='defiant'){
   fill(c,[[0,0],[w*.42,-w*.025,w,0],[w*.86,w*.065,w*.23,w*.07,0,0]],'#f3dfc8');stroke(c,[[0,0],[w*.42,-w*.025,w,0]],spec.ink,w*.02);
  }else stroke(c,[[0,0],[w*.34,w*lip,w*.72,w*lip,w,0]],spec.ink,w*.022);
  stroke(c,[[w*.32,opening+w*.13],[w*.52,opening+w*.16,w*.73,opening+w*.11]],'#ae7e69',w*.012);c.restore();c.restore();
  c.save();c.globalCompositeOperation='destination-in';c.drawImage(mask,0,0);c.restore();
  g.clearRect(0,0,canvas.width,canvas.height);g.drawImage(image,0,0);g.drawImage(layer,0,0);
  return{jaw,emotion,blink,gaze,design:spec.id,occlusion:'source-skin'};
 }
 return{canvas,paint,mask,spec};
}
