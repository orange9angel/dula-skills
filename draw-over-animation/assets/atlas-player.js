// Full-cell atlas playback. No limb slicing, morphing, or claimed motion repair.
export function createAtlasPlayer(image,{columns,rows,count=columns*rows,period=1,exposures=null}){
 if(!Number.isInteger(columns)||!Number.isInteger(rows)||columns<1||rows<1||count<1||count>columns*rows||period<=0)throw Error('Invalid atlas layout');
 const cellWidth=image.width/columns,cellHeight=image.height/rows;
 const total=exposures?.reduce((a,b)=>a+b.duration,0)??period;
 if(exposures?.some(e=>e.frame<0||e.frame>=count||e.duration<=0))throw Error('Invalid atlas exposure');
 function frameAt(t){const time=((t%total)+total)%total;if(!exposures)return Math.min(count-1,Math.floor(time/period*count));let end=0;for(const e of exposures){end+=e.duration;if(time<end)return e.frame;}return exposures.at(-1).frame;}
 function draw(ctx,t,rect,frame=frameAt(t)){ctx.drawImage(image,(frame%columns)*cellWidth,Math.floor(frame/columns)*cellHeight,cellWidth,cellHeight,...rect);return frame;}
 return{frameAt,draw,cellWidth,cellHeight,period:total};
}
