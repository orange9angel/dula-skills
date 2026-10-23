// Gentle scene integration that keeps the authored drawing and silhouette.
// The caller supplies stage coordinates and the matching camera transform.
function ellipseGradient(ctx,x,y,rx,ry,alpha,angle=0){
 ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.scale(rx,ry);
 const gradient=ctx.createRadialGradient(0,0,0,0,0,1);
 gradient.addColorStop(0,`rgba(9,10,22,${alpha})`);gradient.addColorStop(.45,`rgba(9,10,22,${alpha*.68})`);gradient.addColorStop(1,'rgba(9,10,22,0)');
 ctx.fillStyle=gradient;ctx.beginPath();ctx.arc(0,0,1,0,Math.PI*2);ctx.fill();ctx.restore();
}
export function drawGroundContact(ctx,{x,y,radiusX=26,radiusY=5,opacity=.35,cast=[100,-24]}){
 const length=Math.hypot(...cast),angle=Math.atan2(cast[1],cast[0]);
 ellipseGradient(ctx,x+cast[0]*.42,y+cast[1]*.42,length*.64,radiusX*.38,opacity*.38,angle);
 ellipseGradient(ctx,x,y,radiusX*1.25,radiusY*1.55,opacity);
 ellipseGradient(ctx,x,y,radiusX*.58,radiusY*.60,opacity*.6);
}
export function createCelIntegration({width,height}){
 const surface=document.createElement('canvas');surface.width=width;surface.height=height;
 const g=surface.getContext('2d');
 return{draw(ctx,image,{warmPoint=[0,height*.65],warmRadius=width*.7,firePoint=null,firePower=0,time=0}={}){
  g.clearRect(0,0,width,height);g.globalCompositeOperation='source-over';g.drawImage(image,0,0);
  g.globalCompositeOperation='source-atop';g.fillStyle='rgba(35,43,66,.035)';g.fillRect(0,0,width,height);
  const light=g.createRadialGradient(...warmPoint,0,...warmPoint,warmRadius);
  light.addColorStop(0,'rgba(255,173,85,.10)');light.addColorStop(1,'rgba(255,173,85,0)');g.fillStyle=light;g.fillRect(0,0,width,height);
  if(firePoint&&firePower>0){
   const strength=.12*firePower*(.94+.06*Math.sin(time*8.3)),fire=g.createRadialGradient(...firePoint,0,...firePoint,height*.6);
   fire.addColorStop(0,`rgba(255,196,98,${strength})`);fire.addColorStop(1,'rgba(255,196,98,0)');g.fillStyle=fire;g.fillRect(0,0,width,height);
  }
  g.globalCompositeOperation='source-over';ctx.drawImage(surface,0,0);
 }};
}
