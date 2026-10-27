// Reproject an existing absolute-time 3D particle simulation into an authored
// painting. The episode resolves semantic anchors; this module owns projection,
// source color, soft sprites, blending and clipping.
const cache=new Map();
function sprite(r,g,b){
  const key=[r,g,b].map(x=>Math.round(x*31)).join(',');if(cache.has(key))return cache.get(key);
  const c=document.createElement('canvas');c.width=c.height=32;
  const q=c.getContext('2d'),s=q.createRadialGradient(16,16,0,16,16,16);
  const color=[r,g,b].map(x=>Math.round(x*255));s.addColorStop(0,`rgba(${color},1)`);s.addColorStop(.22,`rgba(${color},.6)`);s.addColorStop(1,`rgba(${color},0)`);q.fillStyle=s;q.fillRect(0,0,32,32);cache.set(key,c);return c;
}
export function drawProjectedParticles({THREE,g,systems,camera,width=1280,height=720,resolve}){
  const v=new THREE.Vector3(),project=p=>{v.set(...p).project(camera);return[(v.x+1)*width/2,(1-v.y)*height/2,v.z];};
  let visible=0;g.save();g.globalCompositeOperation='lighter';
  for(const sys of systems){
    if(!sys.points.visible)continue;const rule=resolve(sys,project);if(rule===false)continue;
    const {from,target,scale=1,maxRadius=7,alpha=.55,point}=rule??{};
    for(let i=0;i<sys.count;i++){
      if(sys.al[i]<=.005)continue;
      const raw=[sys.pos[i*3],sys.pos[i*3+1],sys.pos[i*3+2]],p=project(raw);if(!point&&(p[2]<-1||p[2]>1))continue;
      let [x,y]=point?point(raw,i):p;
      if(!point&&target&&from){x=target[0]+(x-from[0])*scale;y=target[1]+(y-from[1])*scale;}
      if(x<-30||x>width+30||y<-30||y>height+30)continue;
      const depth=-v.set(...raw).applyMatrix4(camera.matrixWorldInverse).z;
      const radius=point?maxRadius:Math.max(.7,Math.min(maxRadius,sys.sz[i]*height/(2*Math.tan(camera.fov*Math.PI/360))/Math.max(.2,depth)*scale));
      g.globalAlpha=Math.min(.9,sys.al[i]*alpha);
      g.drawImage(sprite(...sys.col.slice(i*3,i*3+3)),x-radius,y-radius,radius*2,radius*2);visible++;
    }
  }g.restore();return visible;
}
