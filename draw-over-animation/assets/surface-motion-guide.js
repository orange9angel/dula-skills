// EXPERIMENTAL correspondence exporter, not a validated paint propagator.
// Rasterize exact mesh correspondence and reference visibility for keypaint
// propagation. Unlike a projected material, the 2D compositor may retain an
// authored silhouette outside the proxy. CPU deformed positions are supported.
export function createSurfaceMotionGuide({THREE,renderer,scene,root,width,height,depthTolerance=.00015,allowIncomplete=false}){
 if(root.parent!==scene)throw Error('Motion guide currently requires a direct scene child as root');
 const unsupported=mesh=>mesh.isSkinnedMesh||mesh.morphTargetInfluences?.length,excluded=[];root.traverseVisible(m=>{if(m.isMesh&&unsupported(m))excluded.push(m.uuid);});
 if(excluded.length&&!allowIncomplete)throw Error('GPU skin/morph meshes require baked proxies; allowIncomplete marks these surfaces invalid');
 const keys=new Map(),target=new THREE.WebGLRenderTarget(width,height,{depthBuffer:true});
 const matrix=new THREE.Matrix4(),p=new THREE.Vector4(),canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
 const ctx=canvas.getContext('2d'),pixels=new Uint8Array(width*height*4);
 const white=new THREE.MeshBasicMaterial({color:'#ffffff',toneMapped:false});
 const invalid=new THREE.MeshBasicMaterial({color:'#000000',toneMapped:false});
 const material=new THREE.ShaderMaterial({toneMapped:false,depthTest:true,depthWrite:true,uniforms:{referenceDepth:{value:null},tolerance:{value:depthTolerance}},
  vertexShader:'attribute vec4 referenceClip; varying vec4 rclip; void main(){rclip=referenceClip;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader:`precision highp float; varying vec4 rclip; uniform sampler2D referenceDepth;uniform float tolerance;
   void main(){vec3 q=rclip.xyz/rclip.w;vec2 uv=q.xy*.5+.5;if(uv.x<0.||uv.x>1.||uv.y<0.||uv.y>1.)discard;
    float depth=texture2D(referenceDepth,uv).x;if(q.z*.5+.5>depth+tolerance)discard;
    vec2 c=floor(vec2(uv.x,1.-uv.y)*4094.+1.5);float r=floor(c.x/16.);float g=mod(c.x,16.)*16.+floor(c.y/256.);float b=mod(c.y,256.);gl_FragColor=vec4(r,g,b,255.)/255.;}`});
 const isolated=fn=>{const hidden=[],bg=scene.background,override=scene.overrideMaterial;for(const o of scene.children)if(o!==root&&o.visible){hidden.push(o);o.visible=false;}scene.background=new THREE.Color('#000000');try{return fn();}finally{for(const o of hidden)o.visible=true;scene.background=bg;scene.overrideMaterial=override;renderer.setRenderTarget(null);}};
 const png=()=>{renderer.readRenderTargetPixels(target,0,0,width,height,pixels);const data=ctx.createImageData(width,height);for(let y=0;y<height;y++)data.data.set(pixels.subarray((height-1-y)*width*4,(height-y)*width*4),y*width*4);ctx.putImageData(data,0,0);return canvas.toDataURL('image/png').split(',')[1];};
 return {
  limitations:{excludedGPUDeformers:excluded.length},
  captureReference(id,camera){
   if(keys.has(id))throw Error('Duplicate motion reference '+id);
   root.updateWorldMatrix(true,true);camera.updateMatrixWorld(true);const clips=new Map();
   root.traverseVisible(mesh=>{if(!mesh.isMesh||unsupported(mesh))return;const a=mesh.geometry.attributes.position;if(!a)return;
    matrix.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);const data=new Float32Array(a.count*4);
    for(let i=0;i<a.count;i++){p.set(a.getX(i),a.getY(i),a.getZ(i),1).applyMatrix4(matrix);p.toArray(data,i*4);}clips.set(mesh.uuid,new THREE.Float32BufferAttribute(data,4));
   });
   const depth=new THREE.WebGLRenderTarget(width,height,{depthBuffer:true});depth.depthTexture=new THREE.DepthTexture(width,height,THREE.UnsignedIntType);
   isolated(()=>{scene.overrideMaterial=white;renderer.setRenderTarget(depth);renderer.render(scene,camera);});keys.set(id,{clips,depth});
  },
  captureMask(camera){return isolated(()=>{scene.overrideMaterial=white;renderer.setRenderTarget(target);renderer.render(scene,camera);return png();});},
  captureMap(id,camera){const key=keys.get(id);if(!key)throw Error('Unknown reference '+id);const saved=[];material.uniforms.referenceDepth.value=key.depth.depthTexture;
   return isolated(()=>{root.traverseVisible(mesh=>{if(!mesh.isMesh)return;if(!key.clips.has(mesh.uuid)){saved.push([mesh,mesh.geometry,mesh.material,null]);mesh.material=invalid;return;}
    const original=mesh.geometry,g=new THREE.BufferGeometry();if(original.attributes.position.count!==key.clips.get(mesh.uuid).count)throw Error('Mesh topology changed since reference');g.setAttribute('position',original.attributes.position.clone());g.setIndex(original.index?.clone()??null);g.setAttribute('referenceClip',key.clips.get(mesh.uuid).clone());
    saved.push([mesh,original,mesh.material,g]);mesh.geometry=g;mesh.material=material;
   });
   try{scene.overrideMaterial=null;renderer.setRenderTarget(target);renderer.render(scene,camera);return png();}
   finally{for(const [mesh,geometry,mat,g] of saved){mesh.geometry=geometry;mesh.material=mat;g?.dispose();}}
   });
  },
  dispose(){target.dispose();white.dispose();invalid.dispose();material.dispose();for(const k of keys.values())k.depth.dispose();keys.clear();}
 };
}
