"""Fold a source tail into its head, then fit exactly within an ambience cue."""
import numpy as np
def bounded_bed(source,samples,sr,crossfade=1.5,fade_in=1.5,fade_out=1.5):
    k=min(round(crossfade*sr),len(source)//3)
    loop=source[:-k].copy() if k else source.copy()
    if k:
        w=np.linspace(0,1,k)[:,None]
        loop[:k]=source[-k:]*(1-w)+source[:k]*w
    out=np.tile(loop,(int(np.ceil(samples/len(loop))),1))[:samples].copy()
    for seconds,head in [(fade_in,True),(fade_out,False)]:
        n=min(round(seconds*sr),samples//2)
        if n:
            if head:out[:n]*=np.linspace(0,1,n)[:,None]
            else:out[-n:]*=np.linspace(1,0,n)[:,None]
    return out
