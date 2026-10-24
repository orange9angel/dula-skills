// A persistent surface-space damage drawing, independent of shot distance.
export function drawPropCracks(ctx,{center,axisX,axisY,widthRatio=.052,minWidth=1.4,jagged=false},level=1){
 if(level<=0)return;
 const point=([u,v])=>[center[0]+axisX[0]*u+axisY[0]*v,center[1]+axisX[1]*u+axisY[1]*v];
 let cracks=[[[0,1],[-.09,.88],[-.06,.76],[-.14,.63],[-.07,.53],[-.03,.43]],[[.68,.72],[.49,.58],[.51,.49],[.35,.37],[.38,.25],[.25,.12]],[[-.72,.69],[-.65,.56],[-.53,.49],[-.57,.41],[-.44,.33]]];
 if(jagged)cracks=cracks.map((ps,k)=>ps.flatMap((a,i)=>{if(i===ps.length-1)return[a];const b=ps[i+1];return Array.from({length:5},(_,j)=>{const t=j/5,n=Math.sin((i*5+j)*13.17+k*7.9)*.014*Math.sin(t*Math.PI);return[a[0]+(b[0]-a[0])*t+n,a[1]+(b[1]-a[1])*t+n*.3];});}));
 const width=Math.max(minWidth,Math.hypot(...axisX)*widthRatio)*(level>1?1.2:1);
 ctx.save();ctx.globalCompositeOperation='source-atop';ctx.lineJoin='miter';ctx.lineCap='butt';
 for(const [i,points]of cracks.entries()){
  ctx.beginPath();points.map(point).forEach((p,j)=>j?ctx.lineTo(...p):ctx.moveTo(...p));ctx.strokeStyle='#33272b';ctx.lineWidth=width;ctx.stroke();
  ctx.beginPath();points.map(point).forEach((p,j)=>j?ctx.lineTo(p[0]+width*.6,p[1]):ctx.moveTo(p[0]+width*.6,p[1]));ctx.strokeStyle='#f9d386';ctx.lineWidth=width*.25;ctx.stroke();
  const fork=points[3],a=point(fork),b=point([fork[0]+(i===2?-.23:.22),fork[1]-.06]);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.strokeStyle='#4c3530';ctx.lineWidth=width*.4;ctx.stroke();
 }ctx.restore();
}

// One persistent chipped seam projected into each exposed armor surface.
// `clip` is an explicitly reviewed armor polygon; hidden surfaces need no mark.
export function drawArmorDamage(ctx,{center,axisX,axisY,clip,texture},level=1){
 if(level<=0)return;
 const point=([u,v])=>[center[0]+axisX[0]*u+axisY[0]*v,center[1]+axisX[1]*u+axisY[1]*v];
 ctx.save();ctx.globalCompositeOperation='source-atop';
 if(clip){ctx.beginPath();clip.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.clip();}
 if(texture){ctx.transform(axisX[0],axisX[1],axisY[0],axisY[1],center[0],center[1]);ctx.globalAlpha=level>1?1:.9;ctx.drawImage(texture,-1,-1,2,2);ctx.restore();return;}
 const shape=[[-.19,-1],[-.08,-.7],[-.28,-.48],[-.11,-.19],[-.22,.02],[-.09,.27],[-.16,.58],[.03,1],[.13,.64],[.06,.42],[.18,.19],[.07,-.08],[.18,-.33],[.04,-.55],[.08,-.82]];
 const poly=shape.map(point);ctx.beginPath();poly.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.fillStyle=level>1?'#241d23':'#3d3030';ctx.fill();
 const width=Math.max(.8,Math.hypot(...axisY)*.055);ctx.lineWidth=width;ctx.strokeStyle='#b28756';ctx.stroke();
 for(const points of [[[-.1,-.48],[-.52,-.68],[-.76,-.64]],[[.12,.2],[.45,.02],[.64,.12]],[[-.1,.5],[-.42,.65],[-.7,.57]]]){ctx.beginPath();points.map(point).forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.strokeStyle='#30272a';ctx.stroke();}
 ctx.restore();
}
