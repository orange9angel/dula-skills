// A persistent surface-space damage drawing, independent of shot distance.
export function drawPropCracks(ctx,{center,axisX,axisY},level=1){
 if(level<=0)return;
 const point=([u,v])=>[center[0]+axisX[0]*u+axisY[0]*v,center[1]+axisX[1]*u+axisY[1]*v];
 const cracks=[[[0,1],[-.09,.88],[-.06,.76],[-.14,.63],[-.07,.53],[-.03,.43]],[[.68,.72],[.49,.58],[.51,.49],[.35,.37],[.38,.25],[.25,.12]],[[-.72,.69],[-.65,.56],[-.53,.49],[-.57,.41],[-.44,.33]]];
 const width=Math.max(1.4,Math.hypot(...axisX)*.052)*(level>1?1.2:1);
 ctx.save();ctx.globalCompositeOperation='source-atop';ctx.lineJoin='miter';ctx.lineCap='butt';
 for(const [i,points]of cracks.entries()){
  ctx.beginPath();points.map(point).forEach((p,j)=>j?ctx.lineTo(...p):ctx.moveTo(...p));ctx.strokeStyle='#33272b';ctx.lineWidth=width;ctx.stroke();
  ctx.beginPath();points.map(point).forEach((p,j)=>j?ctx.lineTo(p[0]+width*.6,p[1]):ctx.moveTo(p[0]+width*.6,p[1]));ctx.strokeStyle='#f9d386';ctx.lineWidth=width*.25;ctx.stroke();
  const fork=points[3],a=point(fork),b=point([fork[0]+(i===2?-.23:.22),fork[1]-.06]);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.strokeStyle='#4c3530';ctx.lineWidth=width*.4;ctx.stroke();
 }ctx.restore();
}
