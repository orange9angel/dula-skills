import assert from 'node:assert/strict';
import {createStoryState} from '../assets/story-state.js';
import {checkStoryContracts} from '../assets/continuity-check.js';

const cues={TRAP:12,FREE:21};
const director=createStoryState({cues,tracks:{
 shield:[{at:0,value:'held'},{at:{cue:'TRAP'},value:'wedged'},{at:{cue:'FREE'},value:'held'}],
 strain:[{at:0,value:0},{at:12,value:1,duration:1},{at:22,value:0,duration:4}]
}});
// Repeated and out-of-order seeks must not reset a trapped prop or carried emotion.
const times=[0,11.9,12,13,19.9,21,24,30];
const baseline=times.map(t=>director.at(t));
for(const i of [7,1,6,2,5,3,0,4])assert.deepEqual(director.at(times[i]),baseline[i]);
assert.equal(director.at(20).shield,'wedged');
assert.equal(director.at(21).shield,'held');
assert.equal(director.at(19).strain,1);
assert.equal(director.at(24).strain,.5);
assert.throws(()=>createStoryState({cues,tracks:{bad:[{at:{cue:'MISSING'},value:1}]}}),/Unknown story cue/);
assert.throws(()=>createStoryState({cues,tracks:{bad:[{at:2,value:1},{at:1,value:0}]}}),/Invalid state track/);
const contracts=[{id:'prop',at:[{cue:'TRAP',offset:3}],expect:{'shield':{equals:'wedged'}}}];
assert.equal((await checkStoryContracts({sample:t=>director.at(t),contracts,cues})).passed,true);
assert.equal((await checkStoryContracts({sample:()=>({shield:'held'}),contracts,cues})).passed,false);
await assert.rejects(checkStoryContracts({sample:()=>({}),contracts:[{id:'missing',at:[{cue:'UNKNOWN'}],expect:{}}],cues}),/Unresolved contract time/);
console.log('Persistent state seeks, carried emotion and failing contract detection passed.');
