// A generated key painting bound to original mesh surfaces at a reference pose.
// Geometry, deformation, depth and shadows remain the source renderer's.
// Suitable only for the reviewed view range; no arbitrary-angle guarantee.
export function createProjectedRegionPaint({THREE,root,projector,texture,maskTexture,landmarks=[],radius=.16,meshOptions=()=>({})}){
 root.updateWorldMatrix(true,true);projector.updateMatrixWorld(true);
 const project=new THREE.Matrix4().multiplyMatrices(projector.projectionMatrix,projector.matrixWorldInverse);
 const cameraNormal=projector.getWorldDirection(new THREE.Vector3()).negate();
 const coeff=fitLandmarks(landmarks,radius),points=coeff.map(c=>new THREE.Vector4(c[0],c[1],c[2],c[3]));
 const uniforms={rpMap:{value:texture},rpMask:{value:maskTexture},rpBlend:{value:1},rpRadius:{value:radius},rpControls:{value:points.length?points:[new THREE.Vector4()]}};
 const changed=[],p=new THREE.Vector3(),n=new THREE.Vector3(),normalMatrix=new THREE.Matrix3();
 root.traverseVisible(mesh=>{
  if(!mesh.isMesh||!mesh.geometry.attributes.position||!mesh.geometry.attributes.normal)return;
  const options=meshOptions(mesh);if(options===false)return;
  const warp=options.landmarkWarp!==false, rejectWarm=options.rejectWarm===true;
  const skinFallback=options.coolFallback?new THREE.Color(options.coolFallback):null;
  const fallbackRegion=options.coolFallbackRegion??[0,0,1,1];
  const geometry=mesh.geometry.clone(),position=geometry.attributes.position,normal=geometry.attributes.normal,uv=[],facing=[];
  normalMatrix.getNormalMatrix(mesh.matrixWorld);
  for(let i=0;i<position.count;i++){
   p.fromBufferAttribute(position,i).applyMatrix4(mesh.matrixWorld).applyMatrix4(project);uv.push(p.x*.5+.5,p.y*.5+.5);
   n.fromBufferAttribute(normal,i).applyMatrix3(normalMatrix).normalize();facing.push(n.dot(cameraNormal));
  }
  geometry.setAttribute('regionPaintUV',new THREE.Float32BufferAttribute(uv,2));geometry.setAttribute('regionPaintFacing',new THREE.Float32BufferAttribute(facing,1));
  const convert=old=>{
   const material=old.clone(),previous=old.onBeforeCompile?.bind(old),baseKey=old.customProgramCacheKey?.();
   material.onBeforeCompile=(shader,...args)=>{
    previous?.(shader,...args);Object.assign(shader.uniforms,uniforms);
    shader.vertexShader='attribute vec2 regionPaintUV;attribute float regionPaintFacing;varying vec2 vRegionPaintUV;varying float vRegionPaintFacing;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvRegionPaintUV=regionPaintUV;vRegionPaintFacing=regionPaintFacing;');
    shader.fragmentShader=`uniform sampler2D rpMap;uniform sampler2D rpMask;uniform float rpBlend;uniform float rpRadius;uniform vec4 rpControls[${Math.max(1,points.length)}];varying vec2 vRegionPaintUV;varying float vRegionPaintFacing;\n`+shader.fragmentShader;
    const anchor=shader.fragmentShader.includes('#include <opaque_fragment>')?'#include <opaque_fragment>':'#include <output_fragment>';
    if(!shader.fragmentShader.includes(anchor))throw Error('Unsupported material output for region paint');
    shader.fragmentShader=shader.fragmentShader.replace(anchor,`
     vec2 rpUV=vRegionPaintUV;vec2 rpDelta=vec2(0.);
     for(int i=0;i<${warp?points.length:0};i++){vec2 d=rpUV-rpControls[i].xy;rpDelta+=exp(-dot(d,d)/(rpRadius*rpRadius))*rpControls[i].zw;}
     float inside=step(0.,rpUV.x)*step(rpUV.x,1.)*step(0.,rpUV.y)*step(rpUV.y,1.);
     float amount=rpBlend*inside*smoothstep(-.02,.06,vRegionPaintFacing)*smoothstep(.25,.85,texture2D(rpMask,rpUV).r);
     vec4 paint=texture2D(rpMap,rpUV+rpDelta);
     ${rejectWarm?'amount*=1.-smoothstep(-.01,.025,paint.r-paint.b);':''}
     ${skinFallback?`float fallbackArea=step(${fallbackRegion[0].toFixed(6)},rpUV.x)*step(rpUV.x,${fallbackRegion[2].toFixed(6)})*step(${fallbackRegion[1].toFixed(6)},rpUV.y)*step(rpUV.y,${fallbackRegion[3].toFixed(6)});
     paint.rgb=mix(paint.rgb,vec3(${skinFallback.r},${skinFallback.g},${skinFallback.b}),fallbackArea*smoothstep(.005,.025,paint.b-paint.r)*smoothstep(.01,.04,paint.b-paint.g));`:''}
     outgoingLight=mix(outgoingLight,paint.rgb,amount*paint.a);
     ${anchor}`);
   };
   material.customProgramCacheKey=()=>`projected-region-paint-v4-${points.length}-${warp}-${rejectWarm}-${options.coolFallback??''}-${fallbackRegion.join(',')}-${baseKey??''}`;material.needsUpdate=true;return material;
  };
  const oldMaterial=mesh.material,newMaterial=Array.isArray(oldMaterial)?oldMaterial.map(convert):convert(oldMaterial);
  changed.push({mesh,geometry:mesh.geometry,material:oldMaterial,newGeometry:geometry,newMaterial});mesh.geometry=geometry;mesh.material=newMaterial;
 });
 return{setBlend(value){uniforms.rpBlend.value=THREE.MathUtils.clamp(value,0,1);},meshes:changed.map(c=>c.mesh),uniforms,dispose(){for(const c of changed){c.mesh.geometry=c.geometry;c.mesh.material=c.material;c.newGeometry.dispose();for(const m of Array.isArray(c.newMaterial)?c.newMaterial:[c.newMaterial])m.dispose();}}};
}
// Points are [sourceU,sourceV,paintU,paintV], with V increasing upwards.
function fitLandmarks(points,radius){
 if(!points.length)return[];
 const n=points.length,m=points.map((a,i)=>points.map((b,j)=>Math.exp(-((a[0]-b[0])**2+(a[1]-b[1])**2)/(radius*radius))+(i===j?1e-6:0)).concat([a[2]-a[0],a[3]-a[1]]));
 for(let i=0;i<n;i++){let k=i;for(let j=i+1;j<n;j++)if(Math.abs(m[j][i])>Math.abs(m[k][i]))k=j;[m[i],m[k]]=[m[k],m[i]];const d=m[i][i];if(Math.abs(d)<1e-9)throw Error('Degenerate region landmarks');for(let j=i;j<n+2;j++)m[i][j]/=d;for(let k=0;k<n;k++)if(k!==i){const f=m[k][i];for(let j=i;j<n+2;j++)m[k][j]-=f*m[i][j];}}
 return points.map((a,i)=>[a[0],a[1],m[i][n],m[i][n+1]]);
}
