"""Exploratory analysis of the parsed Blue Coat logs (output of parse_bluecoat.py).
Files are grouped by appliance (SGOS version in the log header): A = 001+004, B = 002+003."""
import sys, os, json, numpy as np
P, OUT = sys.argv[1], sys.argv[2]
GROUPS = {'A': ['001', '004'], 'B': ['002', '003']}
TOPK = 2000

def acf(x, lag):
    x = x - x.mean(); d = (x * x).sum()
    return float((x[:-lag] * x[lag:]).sum() / d) if d > 0 and len(x) > lag else float('nan')

files_info, res, arrays = {}, {}, {}
for g, ids in GROUPS.items():
    parts = []
    for i in ids:
        z = np.load(os.path.join(P, f'bluecoat_{i}.npz'))
        acts = z['actions']; a = acts[z['act']]
        ts = z['ts']
        hit = np.char.find(a.astype(str), 'HIT') >= 0
        days, cnt = np.unique(ts // 86400, return_counts=True)
        full = [int(d) for d in days if len(np.unique((ts[ts // 86400 == d] % 86400) // 3600)) == 24]
        files_info[i] = dict(group=g, rows=int(len(ts)),
                             first=str(np.datetime64(int(ts.min()), 's')), last=str(np.datetime64(int(ts.max()), 's')),
                             full_days=[str(np.datetime64(d, 'D')) for d in full],
                             real_hit_ratio_all_pct=100 * float(hit.mean()))
        noncache = (np.char.find(a.astype(str), 'NC_') >= 0) | (np.char.find(a.astype(str), 'ERR') >= 0) | \
                   (np.char.find(a.astype(str), 'DENIED') >= 0)
        okst = np.isin(z['status'], [200, 203, 206, 300, 301, 304])
        keep = z['get'] & okst & ~noncache
        parts.append(dict(ts=ts[keep], obj=z['obj'][keep], size=z['size'][keep], hit=hit[keep]))
    ts = np.concatenate([p['ts'] for p in parts]); o = np.argsort(ts, kind='stable')
    ts = ts[o]; obj = np.concatenate([p['obj'] for p in parts])[o]
    size = np.concatenate([p['size'] for p in parts])[o]; hit = np.concatenate([p['hit'] for p in parts])[o]
    # duplicates between files of the same appliance?
    dup = len(ts) - len(np.unique(np.stack([ts, obj, size]), axis=1)[0]) if len(ts) < 6_000_000 else -1
    t0 = (ts.min() // 86400) * 86400
    H = int((ts.max() - t0) // 3600) + 1
    hourly = np.bincount((ts - t0) // 3600, minlength=H)
    uniq, inv, tot = np.unique(obj, return_inverse=True, return_counts=True)
    N, U = len(obj), len(uniq)
    s = np.sort(tot)[::-1]; cum = np.cumsum(s) / N; r = np.arange(1, U + 1)
    sel = (r >= 10) & (r <= min(100000, U))
    alpha = -np.polyfit(np.log(r[sel]), np.log(s[sel]), 1)[0]
    top = np.argsort(-tot)[:TOPK]
    pos = np.full(U, -1); pos[top] = np.arange(len(top))
    m = pos[inv] >= 0
    M = np.zeros((len(top), H), np.int32)
    np.add.at(M, (pos[inv][m], (ts[m] - t0) // 3600), 1)
    # restrict ACF to the longest run of hours that actually have traffic
    active = hourly > 0
    best, cur, bs, cs = 0, 0, 0, 0
    for k, v in enumerate(active):
        if v:
            if cur == 0: cs = k
            cur += 1
            if cur > best: best, bs = cur, cs
        else: cur = 0
    seg = slice(bs, bs + best)
    a24 = np.array([acf(M[i, seg].astype(float), 24) for i in range(len(top))])
    hod = np.bincount(((ts % 86400) // 3600 + 0) % 24, minlength=24)
    res[g] = dict(files=GROUPS[g], cacheable_requests=int(N), duplicate_rows=int(dup), unique_objects=int(U),
                  one_hit_wonders_pct=100 * float((tot == 1).mean()),
                  max_hit_ratio_infinite_cache_pct=100 * (1 - U / N),
                  real_proxy_hit_ratio_on_cacheable_pct=100 * float(hit.mean()),
                  top1pct_objects_request_share=float(cum[max(1, U // 100) - 1] * 100),
                  top10pct_objects_request_share=float(cum[max(1, U // 10) - 1] * 100),
                  zipf_alpha=float(alpha), longest_continuous_hours=int(best),
                  traffic_acf_lag24=acf(hourly[seg].astype(float), 24),
                  topK=len(top), topK_acf24_median=float(np.nanmedian(a24)),
                  topK_daily_periodic_pct=100 * float(np.nanmean(a24 >= 0.3)))
    arrays[g] = dict(hourly=hourly, popularity=s[:500000], acf24=a24, M=M[:, seg], hod=hod, t0=t0)
    print(g, json.dumps(res[g], indent=1), flush=True)
np.savez_compressed(os.path.join(OUT, 'bc_arrays.npz'), **{f'{g}_{k}': v for g in arrays for k, v in arrays[g].items()})
json.dump(dict(files=files_info, groups=res), open(os.path.join(OUT, 'bc_summary.json'), 'w'), indent=1)
print(json.dumps(files_info, indent=1))
