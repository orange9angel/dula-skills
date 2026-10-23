// Facial drawing on a deliberately blank, angle-specific portrait. Landmarks
// must be authored for each face; this does not erase an existing expression.
const clamp=x=>Math.max(0,Math.min(1,x));
function path(g,points,fill,stroke=null,width=2){g.beginPath();for(const p of points){if(p[0]==='M')g.moveTo(p[1],p[2]);else if(p[0]==='L')g.lineTo(p[1],p[2]);else if(p[0]==='Q')g.quadraticCurveTo(...p.slice(1));else g.closePath();}if(fill){g.fillStyle=fill;g.fill();}if(stroke){g.strokeStyle=stroke;g.lineWidth=width;g.stroke();}}
export function createFacePainter(image,{eyes,mouth,iris='#87522f',direction=1,unit=1}){
 const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;const g=canvas.getContext('2d');
 function paint({jaw=0,emotion='calm',blink=0,gaze=0,intensity=1}={}){
  g.clearRect(0,0,canvas.width,canvas.height);g.drawImage(image,0,0);g.save();g.scale(unit,unit);g.lineCap='round';g.lineJoin='round';
  const angry=['resolve','defiant','shout','threat','cold'].includes(emotion),pain=emotion==='pain',sad=['sad','tired_smile'].includes(emotion),surprise=['surprise','wonder'].includes(emotion),smile=['wry','relief','tired_smile'].includes(emotion);
  const openness=(surprise?1.12:pain?.50:sad?.72:angry?.78:.94)*(1-blink),ink='#35282f';
  for(const [x,y,sx,sy,far] of eyes){
   g.save();g.translate(x,y);g.scale(far?-sx:sx,sy);const h=40*openness,tilt=angry?6:pain?8:sad?-4:0;
   const shape=[['M',-82,6],['L',-66,-h*.65+tilt],['Q',-12,-h-9,33,-h*.65],['L',78,-h*.10],['Q',31,28*openness,-16,26*openness],['Q',-63,24*openness,-82,6],['Z']];
   if(openness>.07){g.save();path(g,shape,'#fff4e2');g.clip();g.fillStyle='#a38583';g.fillRect(-90,-70,180,43);
    const ix=(far?-24:24)*direction+gaze*18*(far?.7:1);g.fillStyle=iris;g.beginPath();g.ellipse(ix,1,25,41,0,0,Math.PI*2);g.fill();g.fillStyle=direction>0?'#bb873e':'#64a4a0';g.beginPath();g.ellipse(ix+2,19,20,21,0,0,Math.PI*2);g.fill();g.fillStyle=ink;g.beginPath();g.ellipse(ix,-2,10,30,0,0,Math.PI*2);g.fill();g.fillStyle='#fff8e6';g.beginPath();g.ellipse(ix-8,-16,6,8,0,0,Math.PI*2);g.fill();g.restore();path(g,shape,null,ink,2.5);path(g,shape.slice(0,4),null,ink,6);
   }else path(g,[['M',-80,0],['Q',-10,17,78,-3]],null,ink,5);
   const slope=(far?-1:1)*direction*(angry?19:pain?13:sad?-17:surprise?-4:7);
   path(g,[['M',-84,-53-slope],['Q',-5,-61,78,-53+slope],['L',76,-45+slope],['Q',-4,-50,-84,-48-slope],['Z']],ink);
   if(pain)path(g,[['M',-67,42],['L',-54,54],['M',-51,41],['L',-37,53]],null,'#aa765f',2);g.restore();
  }
  g.save();g.translate(mouth[0],mouth[1]);g.rotate(mouth[2]||0);const w=42+18*jaw,h=4+60*jaw;
  if(jaw>.06){path(g,[['M',-w,0],['Q',0,-14,w,0],['Q',w-6,h,0,h+5],['Q',-w+8,h,-w,0],['Z']],'#512d36',ink,3);
   path(g,[['M',-w+5,0],['Q',0,-9,w-5,0],['L',w-9,10],['Q',0,6,-w+9,11],['Z']],'#fff2dd');if(jaw>.4)path(g,[['M',-w*.5,h-6],['Q',0,h-23,w*.55,h-4],['Q',0,h+3,-w*.5,h-6],['Z']],'#bd7b7b');
  }else if(pain||emotion==='defiant'){path(g,[['M',-43,0],['Q',0,-8,43,1],['L',37,11],['Q',0,8,-38,11],['Z']],'#fff2dd',ink,2.4);}
  else path(g,[['M',-45,0],['Q',0,smile?15:sad?-4:1,45,smile?-3:1]],null,ink,3);
  path(g,[['M',-15,h+16],['Q',3,h+20,23,h+13]],null,'#b5836c',1.8);g.restore();g.restore();return{jaw,emotion,blink,gaze,intensity};
 }
 return{canvas,paint};
}
