"""Diagnostic for the model design: how well does each signal predict that an object is requested again
within the next hour (H=3600 s)? Measured by AUC on test-period requests (t >= test_start).
Signals: instantaneous ones used by the 2014/2019 papers (recency, frequency, 15-min window count) versus
time-series ones (same hour 1 day / 7 days ago, same window, and their combination)."""
import sys, json, numpy as np
trace = sys.argv[1]; H = 3600
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
r = np.fromfile(trace, dtype=REC); meta = json.load(open(trace + '.json'))
key = (r['id'].astype(np.int64) << 32) | r['t'].astype(np.int64)
o = np.argsort(key, kind='stable'); ks = key[o]; n = len(ks)
ids = r['id'][o]; first = np.ones(n, bool); first[1:] = ids[1:] != ids[:-1]
gs = np.maximum.accumulate(np.where(first, np.arange(n), 0))
def count(a, b):   # requests of the same object with time in (t+a, t+b]
    return (np.searchsorted(ks, ks + b, side='right') - np.searchsorted(ks, ks + a, side='right')).astype(np.float32)
y = count(0, H) > 0                                     # requested again within the next hour
sig = {
  'recency (-time since previous request)': None,
  'frequency so far': (np.arange(n) - gs + 1).astype(np.float32),
  'count last 15 min': count(-900, 0) + 1,
  'count last 1 h': count(-H, 0) + 1,
  'same next-hour window 1 day ago': count(-86400, -86400 + H),
  'same next-hour window 7 days ago': count(-7 * 86400, -7 * 86400 + H),
}
prev = np.empty(n, np.int64); prev[1:] = ks[:-1]; sig['recency (-time since previous request)'] = np.where(first, -1e9, -(ks - prev)).astype(np.float32)
sig['1 day ago + 7 days ago'] = sig['same next-hour window 1 day ago'] + sig['same next-hour window 7 days ago']
sig['last 1 h + 1 day ago (combined)'] = np.log1p(sig['count last 1 h']) + np.log1p(sig['same next-hour window 1 day ago'])
test = (ks & 0xFFFFFFFF) >= meta['test_start']
def auc(s, yy):
    rk = np.empty(len(s)); order = np.argsort(s, kind='mergesort'); ss = s[order]
    # average ranks for ties
    _, first_idx, counts = np.unique(ss, return_index=True, return_counts=True)
    avg = first_idx + (counts - 1) / 2.0 + 1; rk[order] = np.repeat(avg, counts)
    npos = yy.sum(); nneg = len(yy) - npos
    return float((rk[yy].sum() - npos * (npos + 1) / 2) / (npos * nneg))
res = {k: auc(v[test], y[test]) for k, v in sig.items()}
out = dict(trace=trace, horizon_s=H, positive_rate=float(y[test].mean()), auc=res)
json.dump(out, open('results/diag_timeseries_signal_' + trace.split('/')[-1].replace('.bin', '') + '.json', 'w'), indent=1)
for k, v in sorted(res.items(), key=lambda x: -x[1]): print('%.3f  %s' % (v, k))
print('positive rate %.3f' % y[test].mean())

