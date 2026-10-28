// Deterministic small-cel speech exposure from final PCM and known-text timing.
// This chooses authored drawings; it does not deform or invent facial anatomy.
const clamp=x=>Math.max(0,Math.min(1,x));
export function createDialogueFaceTrack({clips,start,end,fps=30}){
 const frames=[];let smooth=0,lastAudible=-1e6,last='rest';
 for(let i=0;i<Math.ceil((end-start)*fps);i++){
  const t=start+i/fps,clip=clips.find(c=>t>=c.start-.04&&t<c.start+c.duration+.15);
  const k=clip?Math.floor((t-clip.start)*clip.energyRate):-1,raw=clip?.energy[k]??0;
  smooth+=(raw-smooth)*(1-Math.exp(-1/fps/(raw>smooth?.025:.075)));
  if(raw>.006)lastAudible=t;
  const voiced=!!clip&&t-lastAudible<.067&&smooth>.006;
  const c=clip?.chars.find(c=>t+.025>=c.start&&t+.025<c.end),phase=c?clamp((t+.025-c.start)/Math.max(.04,c.end-c.start)):0;
  let mouth='rest';
  if(voiced&&c){
   if(['b','p','m'].includes(c.initial)&&t<c.start+.035)mouth='labial';
   else if(/[uüv]|o/.test(c.final)&&!/[aei]/.test(c.final))mouth='round';
   else if(/[ao]/.test(c.final)&&!(/^(i|u)/.test(c.final)&&phase<.20)&&!( /[i]$/.test(c.final)&&phase>.72))mouth='open';
   else mouth='narrow';
  }
  // Retain a drawing for two output frames except precise consonant closure and silence.
  if(i%2&&mouth!=='rest'&&mouth!=='labial'&&last!=='labial'&&last!=='rest')mouth=last;
  frames.push({t,mouth,voiced,raw,smoothed:smooth,char:c?.ch??null,initial:c?.initial??null});last=mouth;
 }
 return {frames,at:t=>frames[Math.max(0,Math.min(frames.length-1,Math.floor((t-start)*fps+1e-6)))],scope:'limited authored viseme drawings, not continuous mesh articulation'};
}
export function blinkExposure(t,starts,{fps=30,close=1,hold=2,open=2}={}){
 for(const at of starts){const f=Math.floor((t-at)*fps+1e-6);if(f>=0&&f<close+hold+open)return f<close||f>=close+hold?'half':'closed';}
 return 'open';
}
