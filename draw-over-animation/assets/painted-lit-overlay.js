import * as THREE from 'three';
// Moving painted parts retain their own material response instead of sampling
// the fixed background's receiver map after they change screen position.
export function createPaintedLitOverlay(canvas){
 const texture=new THREE.Texture(canvas);texture.needsUpdate=true;texture.minFilter=texture.magFilter=THREE.LinearFilter;texture.colorSpace=THREE.NoColorSpace;
 const material=new THREE.ShaderMaterial({transparent:true,depthTest:false,depthWrite:false,uniforms:{source:{value:texture},gain:{value:new THREE.Vector3(1,1,1)}},vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',fragmentShader:'varying vec2 vUv;uniform sampler2D source;uniform vec3 gain;void main(){vec4 c=texture2D(source,vUv);gl_FragColor=vec4(c.rgb*gain,c.a);}'});
 const scene=new THREE.Scene(),camera=new THREE.Camera(),quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);quad.frustumCulled=false;scene.add(quad);
 return{setStrength(u){u=Math.max(0,Math.min(1,u));material.uniforms.gain.value.set(.54+.46*u,.62+.38*u,.79+.21*u);texture.needsUpdate=true;},render(renderer){const old=renderer.autoClear;renderer.autoClear=false;renderer.render(scene,camera);renderer.autoClear=old;}};
}
