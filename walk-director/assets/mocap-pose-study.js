// EXPERIMENTAL: straight-path, fixed-proportion motion study. Foot planting,
// entry/exit blending and weapon-aware arms have NOT passed production review.
// Bounded Acclaim-joint retargeting. The episode supplies scale, path, clock,
// target dimensions and the existing pose setter; this is not a universal rig.
export function installMocapPoseStudy({THREE,actor,data,getTime,rootAt,start,end,dims,alongScale=.64,crossScale=.75,verticalScale=1.20,sourceStart=.05,kneeForward=false,pelvisMotion=false}){
 const old=actor.setPose.bind(actor),frames=data.frames,V=p=>new THREE.Vector3(...p),obj=v=>({x:v.x,y:v.y,z:v.z});
 actor.mesh.updateMatrixWorld(true);
 const soles={};for(const side of ['left','right']){const root=actor.feet[side],inverse=root.matrixWorld.clone().invert(),points=[];root.traverseVisible(mesh=>{if(!mesh.isMesh)return;const matrix=new THREE.Matrix4().multiplyMatrices(inverse,mesh.matrixWorld),a=mesh.geometry.attributes.position;for(let i=0;i<a.count;i++)points.push(new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(matrix));});soles[side]=points;}
 const index0=sourceStart*data.fps,first=frames[Math.floor(index0)],baseRoot=V(first.root);
 const sourceOrigin=(first.lhipjoint[0]+first.rhipjoint[0])*.5;
 const ankleFloor=Math.min(...frames.flatMap(f=>[f.ltibia[1],f.rtibia[1]]));
 const clamp=THREE.MathUtils.clamp,from=rootAt(start),heading=from.yaw,forward=new THREE.Vector3(Math.sin(heading),0,Math.cos(heading)),right=new THREE.Vector3(Math.cos(heading),0,-Math.sin(heading));
 const sample=distance=>{
  const target=baseRoot.z+distance/alongScale;let i=Math.floor(index0);
  while(i<frames.length-2&&frames[i+1].root[2]<target)i++;
  const a=frames[i],b=frames[i+1],u=clamp((target-a.root[2])/(b.root[2]-a.root[2]),0,1),f={};
  for(const k in a)f[k]=V(a[k]).lerp(V(b[k]),u);return {f,index:i+u};
 };
 let last=null;
 actor.setPose=p=>{
  const t=getTime();if(!(t>=start&&t<end)){old(p);return;}
  const root=rootAt(t),distance=(root.x-from.x)*forward.x+(root.z-from.z)*forward.z,{f,index}=sample(distance);
  const hip=f.lhipjoint.clone().add(f.rhipjoint).multiplyScalar(.5),lateral=-(hip.x-sourceOrigin)*crossScale;
  // Source hip orientation was previously discarded while the chest rotated.
  // Keep this opt-in: retargeted sole contact still requires independent review.
  const hipAxis=f.lhipjoint.clone().sub(f.rhipjoint).normalize();
  const pelvisYaw=Math.atan2(hipAxis.z,hipAxis.x),pelvisRoll=-Math.atan2(hipAxis.y,Math.hypot(hipAxis.x,hipAxis.z));
  const hipOffsets={};for(const [side,sign] of [['left',-1],['right',1]])hipOffsets[side]=pelvisMotion?
   new THREE.Vector3(sign*hipAxis.x,-sign*hipAxis.y,-sign*hipAxis.z).multiplyScalar(dims.hipHalf):new THREE.Vector3(sign*dims.hipHalf,0,0);
  p.rootX=root.x+right.x*lateral;p.rootZ=root.z+right.z*lateral;p.yaw=heading;
  let hipY=0;
  const feet={};
  for(const [side,short] of [['left','l'],['right','r']]){
   const ankle=f[short+'tibia'],tip=f[short+'foot'],pitch=clamp(Math.atan2(-(tip.y-ankle.y),tip.z-ankle.z)-.46,-.28,.32);
   const y=dims.footY+Math.max(0,(ankle.y-ankleFloor)*verticalScale);
   const foot=new THREE.Vector3(-(ankle.x-hip.x)*crossScale,Math.max(y,dims.footY+Math.sin(Math.abs(pitch))*(pitch<0?.08:.17)),(ankle.z-hip.z)*alongScale);
   feet[side]=foot;const sign=side==='left'?-1:1;
   hipY=Math.min(hipY,foot.y+Math.sqrt(Math.max(.01,(dims.legA+dims.legB-.003)**2-(foot.x-sign*dims.hipHalf)**2-foot.z**2)));
   p[side+'FootPitch']=pitch;p[side+'FootYaw']=0;
  }
  // Shortening stride changes the required hip height. Copying source Y alone
  // while compressing Z produces a crouch even when the source walk is upright.
  const floorCorrection=Math.min(...['left','right'].map(side=>feet[side].y-dims.footY-Math.sin(Math.abs(p[side+'FootPitch']))*(p[side+'FootPitch']<0?.08:.17)));
  for(const side of ['left','right'])feet[side].y-=floorCorrection;
  for(const [side,short] of [['left','l'],['right','r']]){
   const pitch=p[side+'FootPitch'],c=Math.cos(pitch),s=Math.sin(pitch),minY=Math.min(...soles[side].map(v=>v.y*c-v.z*s));
   const sourceLift=(f[short+'tibia'].y-Math.min(f.ltibia.y,f.rtibia.y))*verticalScale;
   feet[side].y=-minY-.008+sourceLift;
  }
  for(const [side,short,sign] of [['left','l',-1],['right','r',1]]){
   const upper=f[short+'hipjoint'].clone().sub(f[short+'femur']).normalize(),lower=f[short+'tibia'].clone().sub(f[short+'femur']).normalize();
   const reach2=dims.legA**2+dims.legB**2-2*dims.legA*dims.legB*upper.dot(lower),foot=feet[side];
   const offset=hipOffsets[side];hipY=Math.max(hipY,foot.y-offset.y+Math.sqrt(Math.max(.01,reach2-(foot.x-offset.x)**2-(foot.z-offset.z)**2)));
  }
  for(const side of ['left','right']){const foot=feet[side],offset=hipOffsets[side];hipY=Math.min(hipY,foot.y-offset.y+Math.sqrt(Math.max(.01,(dims.legA+dims.legB-.004)**2-(foot.x-offset.x)**2-(foot.z-offset.z)**2)));}
  // Retarget whole-body timing: source shoulder/hip axes drive counter-rotation.
  const shoulderAxis=f.lclavicle.clone().sub(f.rclavicle),torso=f.thorax.clone().sub(hip);
  const yaw=clamp(Math.atan2(shoulderAxis.z,shoulderAxis.x),-.14,.14);
  const roll=clamp(-Math.atan2(shoulderAxis.y,shoulderAxis.x),-.045,.045);
  const pitch=clamp(Math.atan2(torso.z,torso.y),-.015,.10);
  const q=new THREE.Quaternion().setFromEuler(new THREE.Euler(pitch,yaw,roll));
  const translation=new THREE.Vector3(0,hipY,0).sub(new THREE.Vector3(0,dims.hipIdle,0).applyQuaternion(q));
  p.bob=hipY-dims.hipIdle;p.lean=0;p.torsoQuaternion=q;p.torsoPosition=translation;
  for(const [side,short,sign] of [['left','l',-1],['right','r',1]]){
   const h=hipOffsets[side].clone().add(new THREE.Vector3(0,hipY,0)),e=feet[side],axis=e.clone().sub(h),length=axis.length();
   // Bone lengths alone cannot prevent a backwards knee after retargeting.
   // The optional straight-walk pole uses actor-local +Z; this is not a
   // universal pole for turns, crouches or an arbitrary character forward axis.
   const sourcePole=kneeForward?new THREE.Vector3(0,0,1):f[short+'femur'].clone().sub(f[short+'hipjoint']);if(!kneeForward)sourcePole.x*=-1;axis.normalize();
   const pole=sourcePole.addScaledVector(axis,-sourcePole.dot(axis)).normalize();
   const reach=clamp(length,Math.abs(dims.legA-dims.legB)+1e-5,dims.legA+dims.legB-1e-5),along=(dims.legA**2-dims.legB**2+reach**2)/(2*reach);
   const knee=h.clone().addScaledVector(axis,along).addScaledVector(pole,Math.sqrt(Math.max(0,dims.legA**2-along**2)));
   p[side+'Leg']=[h,knee,e].map(obj);
   const shoulder=new THREE.Vector3(sign*dims.shoulderHalf,dims.shoulderY,0).applyQuaternion(q).add(translation);
   const upper=f[short+'humerus'].clone().sub(f[short+'clavicle']);upper.x*=-1;upper.normalize();
   const lower=f[short+'radius'].clone().sub(f[short+'humerus']);lower.x*=-1;lower.normalize();
   const elbow=shoulder.clone().addScaledVector(upper,dims.armA),wrist=elbow.clone().addScaledVector(lower,dims.armB);
   p[side+'Arm']=[shoulder,elbow,wrist].map(obj);
  }
  old(p);last={t,sourceFrame:index,hipY,torso:{pitch,yaw,roll},pelvis:{enabled:pelvisMotion,yaw:pelvisMotion?pelvisYaw:0,roll:pelvisMotion?pelvisRoll:0},pose:structuredClone(p)};
 };
 return {get last(){return last;},dispose(){actor.setPose=old;}};
}
