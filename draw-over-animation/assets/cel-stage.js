// Reusable cel atlas extraction and local mesh acting. Coordinates belong to
// the drawing, while placement/camera remain episode-directed pixel space.
export const clamp=x=>Math.max(0,Math.min(1,x));
export const ease=x=>{x=clamp(x);return x*x*(3-2*x);};
const weight=(u,v,p)=>Math.exp(-2*(((u-p[0])/p[2])**2+((v-p[1])/p[3])**2));
export function extractCel(image,rect=[0,0,1,1],trim=true){
 const c=document.createElement('canvas');c.width=Math.round(image.width*rect[2]);c.height=Math.round(image.height*rect[3]);
 const g=c.getContext('2d',{willReadFrequently:true});g.drawImage(image,image.width*rect[0],image.height*rect[1],c.width,c.height,0,0,c.width,c.height);
 if(!trim)return c;
 const a=g.getImageData(0,0,c.width,c.height).data;let x0=c.width,y0=c.height,x1=0,y1=0;
 for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++)if(a[(y*c.width+x)*4+3]>32){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}
 if(x1<x0||y1<y0)throw Error('Empty cel region');
 const out=document.createElement('canvas');out.width=x1-x0+1;out.height=y1-y0+1;out.getContext('2d').drawImage(c,x0,y0,out.width,out.height,0,0,out.width,out.height);return out;
}
export function separateCelRegions(image,polygons){
 const base=document.createElement('canvas');base.width=image.width;base.height=image.height;const bg=base.getContext('2d');bg.drawImage(image,0,0);
 const parts=polygons.map(points=>{const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const g=c.getContext('2d');g.beginPath();points.forEach((p,i)=>i?g.lineTo(...p):g.moveTo(...p));g.closePath();g.fill();g.lineWidth=18;g.lineJoin='round';g.stroke();g.globalCompositeOperation='source-in';g.drawImage(image,0,0);
  bg.save();bg.globalCompositeOperation='destination-out';bg.beginPath();points.forEach((p,i)=>i?bg.lineTo(...p):bg.moveTo(...p));bg.closePath();bg.fill();bg.lineWidth=24;bg.lineJoin='round';bg.stroke();bg.restore();return c;});
 return{base,parts};
}
export function createCelStage({THREE,renderer,width,height}){
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(0,width,0,height,-100,100),cells=new Map();camera.position.z=10;
 function register(key,image,{dynamic=false,head=[.5,.16,.28,.25],hair=[.5,.08,.4,.13]}={}){
  const texture=new THREE.CanvasTexture(image);texture.colorSpace=THREE.SRGBColorSpace;
  const geo=new THREE.PlaneGeometry(1,1,42,48),mesh=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({map:texture,transparent:true,alphaTest:.018,side:THREE.DoubleSide,depthWrite:false}));
  mesh.frustumCulled=false;scene.add(mesh);cells.set(key,{image,texture,geo,mesh,dynamic,head,hair});
 }
 function begin(){for(const c of cells.values())c.mesh.visible=false;}
 function place(key,{x,y,height:drawHeight,scaleX=1,rotation=0,order=1,view={cx:width/2,cy:height/2,z:1,roll:0},time=0,breath=0,lean=0,headTilt=0,hair=0,compress=0,motion=[0,0],warp=null}){
  const c=cells.get(key);if(!c)throw Error(`Unknown cel ${key}`);const pos=c.geo.attributes.position,uv=c.geo.attributes.uv,scale=drawHeight/c.image.height,w=c.image.width*scale,h=drawHeight;
  c.mesh.visible=true;c.mesh.renderOrder=order;if(c.dynamic)c.texture.needsUpdate=true;
  const cr=Math.cos(rotation),sr=Math.sin(rotation),cv=Math.cos(view.roll||0),sv=Math.sin(view.roll||0);
  for(let i=0;i<pos.count;i++){
   const u=uv.getX(i),v=1-uv.getY(i),upper=1-ease((v-.5)/.48),hw=weight(u,v,c.head),fw=weight(u,v,c.hair);
   const warped=warp?warp(u,v):[0,0];let px=(u-.5)*w*scaleX+warped[0],py=(v-1)*h+warped[1];
   px+=upper*(lean+motion[0])+hw*headTilt*(v-c.head[1])*h+fw*hair;
   py+=upper*(compress+breath*Math.sin(time*2.4)+motion[1])+fw*hair*.22;
   const dx=(x+px*cr-py*sr-view.cx)*view.z,dy=(y+px*sr+py*cr-view.cy)*view.z;
   pos.setXYZ(i,width/2+dx*cv-dy*sv,height/2+dx*sv+dy*cv,0);
  }pos.needsUpdate=true;
 }
 function render(){renderer.render(scene,camera);return renderer.domElement;}
 return{register,begin,place,render,cells};
}
