// Particle-only combat and environment compositor. Effect primitives are
// supplied by dula-assets; episode data owns anchors, times and art direction.
const hash=i=>{const x=Math.sin(i*127.1+311.7)*43758.5453;return x-Math.floor(x);};
export function createParticleEffectsStage({THREE,renderer,particleCloud,combustionBurst,hearthFire,width,height,pixelsPerUnit=200}){
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,.01,100),ppu=pixelsPerUnit;
 const streamGroup=new THREE.Group();scene.add(streamGroup);
 const flame=particleCloud(streamGroup,96,'flame'),smoke=particleCloud(streamGroup,34,'smoke','#686075'),spark=particleCloud(streamGroup,92,'spark');
 const streamClouds=[flame,smoke,spark],fires=new Map(),bursts=new Map(),p=new THREE.Vector3(),velocity=new THREE.Vector3();
 let visibleClouds=[];
 function setView(view){
  const hw=width/(2*ppu*view.z),hh=height/(2*ppu*view.z);
  Object.assign(camera,{left:-hw,right:hw,top:hh,bottom:-hh});camera.position.set(view.cx/ppu,-view.cy/ppu,10);camera.rotation.set(0,0,view.roll??0);camera.updateProjectionMatrix();camera.updateMatrixWorld(true);
 }
 function hide(){streamGroup.visible=false;for(const f of fires.values())f.group.visible=false;for(const b of bursts.values())b.group.visible=false;visibleClouds=[];}
 function render(ctx){
  if(!visibleClouds.length)return;
  for(const c of visibleClouds)c.mesh.visible=c.kind==='smoke';renderer.render(scene,camera);ctx.drawImage(renderer.domElement,0,0);
  for(const c of visibleClouds)c.mesh.visible=c.kind!=='smoke';renderer.render(scene,camera);ctx.save();ctx.globalCompositeOperation='lighter';ctx.globalAlpha=.8;ctx.drawImage(renderer.domElement,0,0);ctx.restore();
  for(const c of visibleClouds)c.mesh.visible=true;
 }
 function drawFire(ctx,t,view,defs){
  hide();setView(view);
  for(const def of defs){
   let f=fires.get(def.id);
   if(!f){const root=new THREE.Group();scene.add(root);const effect=hearthFire(root,new THREE.Vector3());const clouds=[];effect.group.traverse(o=>{if(o.isInstancedMesh)clouds.push({mesh:o,kind:o.name.endsWith('smoke')?'smoke':'fire'});});f={group:root,effect,clouds};fires.set(def.id,f);}
   f.group.visible=true;f.group.position.set(def.base[0]/ppu,-def.base[1]/ppu,0);f.group.scale.setScalar(def.scale??1);f.group.updateMatrixWorld(true);
   f.effect.update(t+(def.seed??0),camera,def.power??1);visibleClouds.push(...f.clouds);
  }
  render(ctx);
 }
 function drawBurst(ctx,t,view,events){
  hide();setView(view);
  for(const e of events){const age=t-e.start;if(age<0||age>1.5)continue;let b=bursts.get(e.id);
   if(!b){const group=new THREE.Group();scene.add(group);const effect=combustionBurst(group,{color:e.color??'#ffd27d',scale:e.scale??.7,normal:new THREE.Vector3(...(e.normal??[0,0,1]))});b={group,effect};bursts.set(e.id,b);}
   b.group.visible=true;b.group.position.set(e.point[0]/ppu,-e.point[1]/ppu,0);b.group.updateMatrixWorld(true);b.effect.update(age,camera);
   visibleClouds.push({mesh:b.effect.sparks.mesh,kind:'fire'},{mesh:b.effect.flames.mesh,kind:'fire'},{mesh:b.effect.smoke.mesh,kind:'smoke'});
  }render(ctx);
 }
 function drawStream(ctx,t,view,{points,progress=1,power=1,start=0,color='#ed8c30',seed=0,flow=false}={}){
  hide();if(!points||points.length<2||power<=0)return;setView(view);streamGroup.visible=true;streamGroup.updateMatrixWorld(true);
  flame.material.uniforms.tint.value.set(color);spark.material.uniforms.tint.value.set(color);
  for(let k=0;k<streamClouds.length;k++){const cloud=streamClouds[k];cloud.begin();
   for(let i=0;i<cloud.mesh.count;i++){
    const r=hash(i+31+k*361+seed),life=(k===1?1.1:.28)+r*(k===1?.8:.46),age=((t-start)+r*life)%life,u=age/life;
    const q=hash(i+177+k*997+seed),at=q*(points.length-1),j=Math.min(points.length-2,Math.floor(at)),f=at-j,a=points[j],b=points[j+1],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy)||1;
    const offset=(hash(i+9)-.5)*(k===1?30:13),drift=age*(k===1?34:48);
    p.set((a[0]+dx*f-dy/len*offset+Math.sin(i+age*7)*age*10)/ppu,-(a[1]+dy*f+dx/len*offset-drift)/ppu,0);
    if(flow){p.x+=age*65*dx/len/ppu;p.y-=age*65*dy/len/ppu;velocity.set(dx/len,-dy/len+.12,0);}
    const fade=q<=progress&&age>=0?Math.sin(Math.PI*u)*power:0;
    if(k===0)cloud.set(i,p,(18+r*22)/ppu,(28+r*42)/ppu,fade*.40,age,r*70,camera,flow?velocity:null);
    else if(k===1){const size=(15+age*32)/ppu;cloud.set(i,p,size,size,fade*.12,age,r*80,camera);}
    else{velocity.set(dx/len*.5,1-dy/len*.5,0);cloud.set(i,p,(1+r)/ppu,(3+r*7)/ppu,fade*.8,age,r*90,camera,velocity);}
   }cloud.end();visibleClouds.push({mesh:cloud.mesh,kind:k===1?'smoke':'fire'});
  }render(ctx);
 }
 return{drawFire,drawBurst,drawStream,counts:{stream:222},scene,camera};
}
