"""Control-rate smoothing for sample-rate audio gains, avoiding huge kernels."""
import numpy as np
from scipy.ndimage import gaussian_filter1d
def smooth_activity(activity,sr,sigma_seconds=.075,control_rate=200):
    hop=max(1,round(sr/control_rate));n=len(activity);pad=(-n)%hop
    blocks=np.pad(activity,(0,pad)).reshape(-1,hop).max(axis=1)
    low=gaussian_filter1d(blocks,sigma_seconds*sr/hop)
    return np.interp(np.arange(n,dtype=np.float64)/hop,np.arange(len(low)),low).astype(np.float32)
