// Fixed-camera painted scene with original 3D performers and a real shadow receiver.
// A backplate is not a reconstructed 3D set; new camera directions need new plates.
export function createPaintedBackplateStage({THREE,scene,actors,canvas,groundY=-.01,shadowOpacity=.28}){
 const keep=new Set(actors.map(a=>a.mesh??a));
 const environment=scene.children.filter(o=>!keep.has(o)&&!o.isLight);
 const originalVisibility=environment.map(o=>o.visible);
 const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
 const oldBackground=scene.background,oldFog=scene.fog;
 const floor=new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.ShadowMaterial({opacity:shadowOpacity}));
 floor.rotation.x=-Math.PI/2;floor.position.y=groundY;floor.receiveShadow=true;floor.name='painted-backplate-shadow-receiver';scene.add(floor);
 function update(){for(const o of environment)o.visible=false;scene.background=texture;scene.fog=null;texture.needsUpdate=true;}
 function dispose(){environment.forEach((o,i)=>o.visible=originalVisibility[i]);scene.remove(floor);floor.geometry.dispose();floor.material.dispose();texture.dispose();scene.background=oldBackground;scene.fog=oldFog;}
 return{update,dispose,floor,texture,scope:'fixed-camera backplate; 3D performers and shadows'};
}
