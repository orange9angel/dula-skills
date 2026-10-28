import * as THREE from 'three';
// Fixed-camera lighting study. Keep the master's geometry and high-frequency
// drawing immutable; transfer only a smooth, bounded illumination ratio from a
// separately art-directed endpoint. This is not geometry-aware moving relighting.
export function createPaintedLightField({bright,dim,width,height,blur=5}){
 if(bright.naturalWidth!==dim.naturalWidth||bright.naturalHeight!==dim.naturalHeight)throw Error('Light endpoints must have equal dimensions');
 const read=im=>{const c=document.createElement('canvas');c.width=width;c.height=height;const g=c.getContext('2d',{willReadFrequently:true});g.filter=`blur(${blur}px)`;g.drawImage(im,-blur,-blur,width+2*blur,height+2*blur);return g.getImageData(0,0,width,height).data;};
 const a=read(bright),b=read(dim),data=new Uint8Array(width*height*4);
 for(let i=0;i<data.length;i+=4){for(let k=0;k<3;k++)data[i+k]=Math.round(127.5*Math.max(.12,Math.min(1.8,(b[i+k]+6)/(a[i+k]+6))));data[i+3]=255;}
 const ratio=new THREE.DataTexture(data,width,height,THREE.RGBAFormat);ratio.needsUpdate=true;ratio.flipY=true;ratio.minFilter=ratio.magFilter=THREE.LinearFilter;
 const base=new THREE.Texture(bright);base.needsUpdate=true;base.minFilter=base.magFilter=THREE.LinearFilter;base.colorSpace=THREE.NoColorSpace;
 const material=new THREE.ShaderMaterial({depthTest:false,depthWrite:false,uniforms:{base:{value:base},ratio:{value:ratio},strength:{value:1}},vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',fragmentShader:'varying vec2 vUv;uniform sampler2D base;uniform sampler2D ratio;uniform float strength;void main(){vec3 c=texture2D(base,vUv).rgb;vec3 r=texture2D(ratio,vUv).rgb*2.;gl_FragColor=vec4(clamp(c*mix(r,vec3(1.),strength),0.,1.),1.);}'});
 const scene=new THREE.Scene(),camera=new THREE.Camera(),quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);quad.frustumCulled=false;scene.add(quad);
 return {scene,camera,material,setStrength:u=>material.uniforms.strength.value=Math.max(0,Math.min(1,u)),dispose(){ratio.dispose();base.dispose();material.dispose();quad.geometry.dispose();}};
}
