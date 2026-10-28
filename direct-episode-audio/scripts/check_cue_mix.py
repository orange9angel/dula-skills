"""Verify an exported cue mix: stems, event transients and encoded audio."""
import argparse, json
from pathlib import Path
import numpy as np
from mix_cue_recipe import read

p=argparse.ArgumentParser(__doc__);p.add_argument('episode',type=Path);p.add_argument('--config',required=True);p.add_argument('--video',required=True);p.add_argument('--output',required=True);a=p.parse_args()
root=a.episode.resolve();c=json.loads((root/a.config).read_text(encoding='utf-8'));report=json.loads((root/c['report']).read_text(encoding='utf-8'));sr=report['sampleRate'];folder=root/c['outputDirectory']
stems={k:read(folder/(k+'.wav'),sr) for k in ['dialogue','foley','ambience','music']};mix=read(folder/'mixed.wav',sr);encoded=read(root/a.video,sr);n=min(len(mix),len(encoded))
summation=float(np.max(np.abs(sum(stems.values())-mix)));peak=float(np.max(np.abs(encoded)));corr=float(np.corrcoef(mix[:n].ravel(),encoded[:n].ravel())[0,1])
# Measure Foley alone, so a louder syllable or chord cannot satisfy an event.
mono=stems['foley'].mean(axis=1);hop=sr//100;env=np.sqrt(np.mean(mono[:len(mono)//hop*hop].reshape(-1,hop)**2,axis=1));change=np.maximum(0,np.diff(env,prepend=0));events=[]
for source in report['sources']:
    if source['id'] not in [t['id'] for t in c['tracks'] if t['bus']=='foley']:continue
    for e in source['placements']:
        local=e['time']-report['start'];i=round(local*100);lo=max(0,i-15);hi=min(len(change),i+16)
        window=change[lo:hi];strength=float(window.max());onset=(lo+int(np.argmax(window)))/100
        events.append({'target':e['time'],'onset':onset+report['start'],'offset':onset-local,'strength':strength,'passed':strength>.0005})
passed=peak<=.8 and corr>.995 and summation<1e-6 and all(e['passed'] for e in events)
result={'passed':passed,'aacPeak':peak,'zeroLagCorrelation':corr,'stemSumError':summation,'referenceSamples':len(mix),'decodedSamples':len(encoded),'events':events,'scope':'technical audio checks, not listening or acting approval'}
(root/a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if passed else 1)
