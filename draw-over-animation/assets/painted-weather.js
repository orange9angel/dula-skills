// Deterministic layered particles and painted cloud sprites. No advancing RNG.
const sat=x=>Math.max(0,Math.min(1,x));
const frac=x=>x-Math.floor(x);
const rnd=(i,k=0)=>frac(Math.sin(i*127.1+k*311.7)*43758.5453);
export function radialLight(g,x,y,r,color,alpha=.1){
  if(alpha<=0)return;g.save();g.globalCompositeOperation='lighter';g.globalAlpha=alpha;
  const q=g.createRadialGradient(x,y,0,x,y,r);q.addColorStop(0,color);q.addColorStop(1,'rgba(0,0,0,0)');
  g.fillStyle=q;g.fillRect(x-r,y-r,r*2,r*2);g.restore();
}
export function cloudTransmission(t){return .78+.12*Math.sin(t*.047)+.07*Math.sin(t*.113+1.3);}
export function drawPaintedClouds(g,image,camera,t,{tower=false,warm=false}={}){
  if(!image)return;
  g.save();g.translate(camera.x,camera.y);g.scale(camera.scale,camera.scale);
  // Behind architecture: the clock tower is an explicitly excluded occluder.
  g.beginPath();g.rect(0,0,1920,tower?670:570);
  if(!tower){g.moveTo(878,0);g.lineTo(1052,0);g.lineTo(1052,570);g.lineTo(878,570);g.closePath();}
  g.clip('evenodd');
  if(warm)g.filter='sepia(.55) saturate(.75) brightness(1.4)';
  const layerH=image.height/3;
  for(let l=0;l<3;l++){
    const w=1700+l*180,h=145+l*35,y=145+l*140;
    const offset=((t*(3+l*2.3)+l*530)%(w+600))-w;
    g.globalAlpha=tower?.23+l*.055:.14+l*.035;
    for(let tile=0;tile<3;tile++)g.drawImage(image,0,l*layerH,image.width,layerH,offset+tile*(w+350),y,w,h);
  }g.restore();
}
export function drawWeatherParticles(g,t,{width=1280,height=720,kind='snow',foreground=false,strength=1,wind=1}={}){
  if(strength<=0)return 0;
  const count=kind==='snow'?(foreground?34:150):kind==='petal'?(foreground?18:55):70;
  let drawn=0;g.save();
  for(let i=0;i<count;i++){
    const seed=i+(foreground?1000:0),z=.25+.75*rnd(seed,1);
    const speed=(kind==='dust'?4:kind==='petal'?18:22)*(foreground?2:1)*(.5+z);
    const x=frac(rnd(seed,2)+t*.0008*wind*(.6+z)+Math.sin(t*.19+rnd(seed,4)*6.28)*.004)*width;
    const y=frac(rnd(seed,3)+t*speed/(height+20))*(height+20)-10;
    const fade=sat(y/35)*sat((height-y)/50),alpha=(foreground?.45:.24)*z*strength*fade;
    const r=(kind==='petal'?2.5:kind==='dust'?.8:1)*(foreground?2.6:1)*(.4+z);
    if(alpha<.005)continue;drawn++;
    g.fillStyle=kind==='petal'?`rgba(255,202,208,${alpha})`:kind==='dust'?`rgba(255,218,153,${alpha})`:`rgba(219,233,248,${alpha})`;
    g.beginPath();g.ellipse(x,y,r,r*(kind==='petal'?.35:1),Math.sin(t*.7+seed)*1.4,0,Math.PI*2);g.fill();
  }g.restore();return drawn;
}
