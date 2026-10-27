// Export the contact clock used by the final painted actor, for audio placement.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {contactSchedule,pathPoint} from '../../draw-over-animation/assets/painted-space.js';
const [configFile,output]=process.argv.slice(2);if(!configFile||!output)throw Error('Usage: export_painted_contacts.mjs staging.json output.json');
const raw=fs.readFileSync(configFile),cfg=JSON.parse(raw),rows=[];
for(const [shot,s] of Object.entries(cfg.shots))for(const [actor,a] of Object.entries(s.actors)){
 if(!a.walk)continue;
 for(const c of contactSchedule(a,s.start,s.end))rows.push({shot,actor,scene:s.scene,...c,plate:pathPoint(a,c.time,s.start,s.end).position});
}
const hash=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
fs.writeFileSync(output,JSON.stringify({schema:'painted-contacts-v1',source:configFile,sha256:hash(configFile),runtimeSha256:hash(new URL('../../draw-over-animation/assets/painted-space.js',import.meta.url)),contacts:rows},null,2));
console.log(`${rows.length} finite contacts -> ${output}`);
