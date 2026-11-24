"""Per-request features for the learning-augmented baselines (Benadit et al. 2014 / Pernabas et al. 2019).
Causal features (only the past is used):
  x1 recency      : seconds since the object's previous request (first request -> 86400)
  x2 frequency    : number of requests of the object so far (including this one)
  x3 sw_frequency : requests of the object within the backward sliding window (SWL = 15 min)
  x4 retrieval    : recorded retrieval time (time-to-first-byte / time-taken), seconds
  x5 size         : object size, bytes
  (x6 object type is not available in the Wikipedia text trace: all objects are pages -> omitted)
Label b = 1 if the object is requested again within the forward sliding window (next 15 min), else 0.
Also stored: prev_gap (time between the previous two requests) for the DMCM weight policy.
usage: python3 scripts/features.py data/processed/<trace>.bin [SWL_seconds]"""
import sys, numpy as np
path = sys.argv[1]; SWL = int(sys.argv[2]) if len(sys.argv) > 2 else 900
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
r = np.fromfile(path, dtype=REC); n = len(r)
key = (r['id'].astype(np.int64) << 32) | r['t'].astype(np.int64)
o = np.argsort(key, kind='stable')          # object-major, time-ordered within an object
ks = key[o]; ids = r['id'][o]; ts = r['t'][o].astype(np.int64)
first = np.ones(n, bool); first[1:] = ids[1:] != ids[:-1]
last = np.ones(n, bool); last[:-1] = ids[1:] != ids[:-1]
grp_start = np.maximum.accumulate(np.where(first, np.arange(n), 0))
freq = (np.arange(n) - grp_start + 1).astype(np.float32)
prev_t = np.empty(n, np.int64); prev_t[1:] = ts[:-1]; prev_t[first] = -1
rec = np.where(first, 86400, ts - prev_t).astype(np.float32)
prev2 = np.empty(n, np.int64); prev2[2:] = ts[:-2]; second = np.zeros(n, bool); second[1:] = first[:-1]
prev_gap = np.where(first | second, 0, prev_t - prev2).astype(np.float32)
lo = np.searchsorted(ks, ks - SWL, side='right')   # same object (key shift stays inside the object's range)
swf = (np.arange(n) - np.maximum(lo, grp_start) + 1).astype(np.float32)
next_t = np.empty(n, np.int64); next_t[:-1] = ts[1:]; next_t[last] = -1
label = (~last) & (next_t - ts <= SWL)
inv = np.empty(n, np.int64); inv[o] = np.arange(n)          # back to trace order
X = np.stack([rec[inv], freq[inv], swf[inv], r['cost'], r['size'].astype(np.float32)], axis=1)
np.savez(path.replace('.bin', f'_feat{SWL}.npz'), X=X, y=label[inv], prev_gap=prev_gap[inv], t=r['t'])
print(path, 'requests', n, 'positive label rate %.3f' % label.mean())
