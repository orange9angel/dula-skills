import assert from 'node:assert/strict';
import {paintedCamera,contactSchedule,travelProgress,actorInPlate} from '../assets/painted-space.js';
// Edge targets, including off-plate requests, must share one corrected transform.
for(const center of [[1680,100,2.2],[1100,800,1.8],[-300,1700,.7],[960,540,1]]){
 const c=paintedCamera({from:center},2,0,4);
 assert(c.x<=0&&c.y<=0&&c.x+1920*c.scale>=1280&&c.y+1080*c.scale>=720);
 const p=[941,779],back=c.inverse(c.point(p));assert(Math.abs(back[0]-p[0])<1e-8&&Math.abs(back[1]-p[1])<1e-8);
}
const a={at:[1200,1000,250],to:[960,780,50],walk:{start:2,end:8,steps:12}};
const contacts=contactSchedule(a,0,10);assert.equal(contacts.length,12);
for(let i=0;i<contacts.length;i++){
 assert(Math.abs(travelProgress(contacts[i].time,2,8)-(i+1)/12)<1e-8);
 if(i)assert(contacts[i].time>contacts[i-1].time);
}
assert.equal(travelProgress(-2,2,8),0);assert.equal(travelProgress(20,2,8),1);
const c=paintedCamera({},0,0,10),end=actorInPlate(a,20,0,10,c);
assert.deepEqual(end.plate,a.to);assert.equal(end.phase,6);
console.log('painted-space: camera coverage/inverse, finite contact clock and stop position passed');
