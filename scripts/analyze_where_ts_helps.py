"""Where does the time-series feature group help? Compare per-request hits of TS-GD(I) vs TS-GD(IT) on the test period,
split by (a) object popularity in the warm-up period, (b) daily periodicity of the object (ACF at 24 h over the warm-up
hourly counts, objects with >= 100 warm-up requests), (c) gap since the object's previous request.
usage: python3 scripts/analyze_where_ts_helps.py trace.bin hitsA.u8 hitsB.u8 labelA labelB"""
import sys, json, numpy as np
trace, fa, fb, la, lb = sys.argv[1:6]
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
r = np.fromfile(trace, dtype=REC); meta = json.load(open(trace + '.json')); W = meta['warmup_end']
A = np.fromfile(fa, np.uint8).astype(bool); B = np.fromfile(fb, np.uint8).astype(bool)
t, ids = r['t'].astype(np.int64), r['id']; test = t >= meta['test_start']; nobj = int(ids.max()) + 1
warm = t < W
pop = np.bincount(ids[warm], minlength=nobj)
# previous-request gap (trace order)
o = np.lexsort((t, ids)); prev = np.full(len(t), -1, np.int64)
same = ids[o][1:] == ids[o][:-1]; prev[o[1:][same]] = t[o[:-1][same]]
gap = np.where(prev < 0, -1, t - prev)
# periodicity of objects with >= 100 warm-up requests
big = np.flatnonzero(pop >= 100); H = W // 3600; pos = np.full(nobj, -1); pos[big] = np.arange(len(big))
m = warm & (pos[ids] >= 0); M = np.zeros((len(big), H), np.int32); np.add.at(M, (pos[ids[m]], t[m] // 3600), 1)
X = M - M.mean(1, keepdims=True); acf = (X[:, :-24] * X[:, 24:]).sum(1) / np.maximum((X * X).sum(1), 1e-9)
obj_acf = np.full(nobj, np.nan); obj_acf[big] = acf
def table(name, cats, labels):
    rows = []; tot = test.sum(); dsum = (B[test].astype(int) - A[test]).sum()
    for c, lab in enumerate(labels):
        s = test & (cats == c); k = s.sum()
        if k == 0: continue
        ha, hb = A[s].mean(), B[s].mean(); d = int(B[s].sum()) - int(A[s].sum())
        rows.append(dict(group=name, category=lab, share_of_test_requests=round(100 * k / tot, 1), HR_A=round(100 * ha, 2), HR_B=round(100 * hb, 2),
                         diff_points=round(100 * (hb - ha), 2), share_of_total_gain=round(100 * d / dsum, 1) if dsum else None))
    return rows
pc = np.digitize(pop[ids], [1, 10, 100, 1000])            # 0: new, 1: 1-9, 2: 10-99, 3: 100-999, 4: 1000+
ac = np.where(np.isnan(obj_acf[ids]), 0, np.digitize(np.nan_to_num(obj_acf[ids]), [0.1, 0.3, 0.5]) + 1)
gc = np.where(gap < 0, 0, np.digitize(gap, [900, 3600, 6 * 3600, 86400]) + 1)
res = table('warm-up popularity', pc, ['new (0)', '1-9', '10-99', '100-999', '1000+']) + \
      table('daily periodicity (ACF24)', ac, ['too few requests (<100)', '< 0.1', '0.1-0.3', '0.3-0.5', '>= 0.5']) + \
      table('gap since previous request', gc, ['first request', '< 15 min', '15 min - 1 h', '1 - 6 h', '6 - 24 h', '> 24 h'])
summary = dict(trace=trace.split('/')[-1], A=la, B=lb, HR_A=float(A[test].mean()), HR_B=float(B[test].mean()), rows=res)
json.dump(summary, open(f'results/where_ts_helps_{la}_vs_{lb}.json', 'w'), indent=1)
print(f"{la}: {100*A[test].mean():.2f}  {lb}: {100*B[test].mean():.2f}")
cur = None
for x in res:
    if x['group'] != cur: cur = x['group']; print(f"\n[{cur}]  {'category':<26}{'share%':>7}{la:>8}{lb:>8}{'diff':>7}{'%gain':>7}")
    print(f"    {x['category']:<34}{x['share_of_test_requests']:>7}{x['HR_A']:>8}{x['HR_B']:>8}{x['diff_points']:>7}{x['share_of_total_gain'] if x['share_of_total_gain'] is not None else '-':>7}")
