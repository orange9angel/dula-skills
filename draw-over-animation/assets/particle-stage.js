// Adapt an existing THREE particle effect to a pixel-space cel stage.
// The effect factory remains owned by the asset library; this module handles
// camera mapping and splits particles around the character's drawing plane.
export function createParticleStage({THREE,renderer,makeAura,width,height,pixelsPerUnit=200,radialScale=1.65}){
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,.01,100);
 const aura=makeAura(scene),clouds=[aura.flame,aura.smoke,aura.embers];
 aura.group.scale.set(radialScale,1,1);
 const saved=clouds.map(c=>new Float32Array(c.mesh.count));let active=false;
 function update(t,{view,base,power,start,height:riseHeight=1.85,color='#ffbf5b'}){
  const halfW=width/(2*pixelsPerUnit*view.z),halfH=height/(2*pixelsPerUnit*view.z);
  camera.left=-halfW;camera.right=halfW;camera.top=halfH;camera.bottom=-halfH;
  camera.position.set(view.cx/pixelsPerUnit,-view.cy/pixelsPerUnit,10);camera.rotation.set(0,0,view.roll??0);
  camera.updateProjectionMatrix();camera.updateMatrixWorld(true);
  active=power>.0001;
  aura.update(t,camera,active?{base:new THREE.Vector3(base[0]/pixelsPerUnit,-base[1]/pixelsPerUnit,0),power,start,height:riseHeight,color}:null);
  for(let c=0;c<clouds.length;c++)for(let i=0;i<clouds[c].mesh.count;i++)saved[c][i]=clouds[c].data[i*3];
 }
 function draw(ctx,layer,{frontOpacity=.36}={}){
  if(!active)return;
  for(let c=0;c<clouds.length;c++){
   const cloud=clouds[c],matrices=cloud.mesh.instanceMatrix.array;
   for(let i=0;i<cloud.mesh.count;i++){
    const inFront=matrices[i*16+14]>=0;
    cloud.data[i*3]=(layer==='front'?inFront:!inFront)?saved[c][i]*(layer==='front'?frontOpacity:1):0;
   }
   cloud.mesh.geometry.attributes.particleData.needsUpdate=true;
  }
  // Smoke absorbs over the background; emissive flames add radiance. Keeping
  // both in one source-over RGBA pass makes a bright source effect look dull.
  clouds.forEach((c,i)=>c.mesh.visible=i===1);
  renderer.render(scene,camera);ctx.drawImage(renderer.domElement,0,0);
  clouds.forEach((c,i)=>c.mesh.visible=i!==1);
  renderer.render(scene,camera);ctx.save();ctx.globalCompositeOperation='lighter';ctx.drawImage(renderer.domElement,0,0);ctx.restore();
  clouds.forEach(c=>c.mesh.visible=true);
 }
 return{update,draw,scene,camera,aura,counts:clouds.map(c=>c.mesh.count)};
}
