"""Exploratory analysis of the Wikipedia CDN 2019 text trace (cache-t).
Pass 1: per-day stats + global popularity. Pass 2: hourly series of the top-K objects.
Memory-safe: one day (~10M rows) in memory at a time."""
import sys, os, glob, json, numpy as np, pandas as pd

DATA = sys.argv[1]            # folder with cache-t-XX.gz
OUT = sys.argv[2]             # results folder
TOPK = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
files = sorted(glob.glob(os.path.join(DATA, 'cache-t-*.gz')))
HOURS = 24 * len(files)
os.makedirs(OUT, exist_ok=True)

def load(f):
    return pd.read_csv(f, sep='\t', header=0, names=['t', 'id', 'size', 'tfb'],
                       dtype={'t': np.int32, 'id': np.int32, 'size': np.int64, 'tfb': np.float32}, engine='c')

CK1 = os.path.join(OUT, 'wiki_pass1.npz')
MODE = sys.argv[4] if len(sys.argv) > 4 else 'all'   # 'pass1' | 'pass2:<from>:<to>' | 'final' | 'all'
hourly = np.zeros(HOURS, np.int64)
hourly_bytes = np.zeros(HOURS, np.int64)
day_ids, day_cnt, per_day, top_by_day = [], [], [], []
for d, f in enumerate(files if not os.path.exists(CK1) else []):
    df = load(f)
    h = (df.t.values // 3600).astype(np.int64)
    h = np.clip(h, 0, HOURS - 1)
    hourly += np.bincount(h, minlength=HOURS)
    hourly_bytes += np.bincount(h, weights=df['size'].values, minlength=HOURS).astype(np.int64)
    ids, cnt = np.unique(df.id.values, return_counts=True)
    day_ids.append(ids); day_cnt.append(cnt.astype(np.int32))
    top_by_day.append(set(ids[np.argsort(-cnt)[:1000]].tolist()))
    per_day.append(dict(day=d, requests=int(len(df)), unique=int(len(ids)),
                        GB=float(df['size'].sum() / 1e9), mean_size_KB=float(df['size'].mean() / 1e3),
                        median_tfb_ms=float(np.median(df.tfb.values) * 1e3)))
    print('day', d, per_day[-1], flush=True)
    del df, h

if not os.path.exists(CK1):
    allids = np.concatenate(day_ids); allcnt = np.concatenate(day_cnt)
    del day_ids, day_cnt
    order = np.argsort(allids, kind='stable')
    allids, allcnt = allids[order], allcnt[order]
    uniq, start = np.unique(allids, return_index=True)
    tot = np.add.reduceat(allcnt.astype(np.int64), start)
    days_active = np.diff(np.append(start, len(allids)))
    del allids, allcnt, order
    np.savez(CK1, uniq=uniq, tot=tot, days_active=days_active, hourly=hourly, hourly_bytes=hourly_bytes,
             per_day=json.dumps(per_day), top_by_day=json.dumps([sorted(x) for x in top_by_day]))
    print('pass1 saved', flush=True)
    if MODE == 'pass1': sys.exit(0)
z = np.load(CK1)
uniq, tot, days_active, hourly, hourly_bytes = z['uniq'], z['tot'], z['days_active'], z['hourly'], z['hourly_bytes']
per_day = json.loads(str(z['per_day'])); top_by_day = [set(x) for x in json.loads(str(z['top_by_day']))]
N = int(tot.sum()); U = len(uniq)
s = np.sort(tot)[::-1]
cum = np.cumsum(s) / N
ranks = np.arange(1, U + 1)
sel = (ranks >= 10) & (ranks <= 100000)
alpha = -np.polyfit(np.log(ranks[sel]), np.log(s[sel]), 1)[0]

def acf(x, lag):
    x = x - x.mean(); d = (x * x).sum()
    return float((x[:-lag] * x[lag:]).sum() / d) if d > 0 else 0.0

jacc = [len(top_by_day[i] & top_by_day[i + 1]) / len(top_by_day[i] | top_by_day[i + 1]) for i in range(len(files) - 1)]
summary = dict(
    days=len(files), requests=N, unique_objects=U,
    one_hit_wonders_pct=100 * float((tot == 1).mean()),
    max_hit_ratio_infinite_cache_pct=100 * (1 - U / N),
    top1pct_objects_request_share=float(cum[max(1, U // 100) - 1] * 100),
    top10pct_objects_request_share=float(cum[max(1, U // 10) - 1] * 100),
    zipf_alpha=float(alpha),
    objects_active_1_day_pct=100 * float((days_active == 1).mean()),
    objects_active_all_days_pct=100 * float((days_active == len(files)).mean()),
    traffic_acf_lag24=acf(hourly.astype(float), 24), traffic_acf_lag168=acf(hourly.astype(float), 168),
    top1000_jaccard_consecutive_days_mean=float(np.mean(jacc)),
)
print(json.dumps(summary, indent=1), flush=True)

# Pass 2: hourly matrix for top-K objects
topk = uniq[np.argsort(-tot)[:TOPK]]
topk_sorted = np.sort(topk)
M = np.zeros((TOPK, HOURS), np.int32)
TMP = os.path.join(OUT, 'wiki_pass2'); os.makedirs(TMP, exist_ok=True)
d0, d1 = (int(MODE.split(':')[1]), int(MODE.split(':')[2])) if MODE.startswith('pass2') else (0, len(files))
for d, f in enumerate(files):
    ck = os.path.join(TMP, f'M_{d:02d}.npy')
    if os.path.exists(ck):
        M += np.load(ck); continue
    if not (d0 <= d < d1):
        continue
    Md = np.zeros((TOPK, HOURS), np.int32)
    df = load(f)
    m = np.isin(df.id.values, topk_sorted)
    idx = np.searchsorted(topk_sorted, df.id.values[m])
    h = np.clip(df.t.values[m] // 3600, 0, HOURS - 1)
    np.add.at(Md, (idx, h), 1)
    np.save(ck, Md); M += Md
    del df, Md
    print('pass2 day', d, flush=True)
if MODE.startswith('pass2'): sys.exit(0)
if len([x for x in os.listdir(TMP) if x.startswith('M_')]) < len(files): sys.exit('pass2 incomplete')
obj_acf24 = np.array([acf(M[i].astype(float), 24) for i in range(TOPK)])
obj_acf168 = np.array([acf(M[i].astype(float), 168) for i in range(TOPK)])
summary.update(dict(
    topK=TOPK, topK_request_share_pct=100 * float(M.sum() / N),
    topK_acf24_median=float(np.median(obj_acf24)),
    topK_daily_periodic_pct=100 * float((obj_acf24 >= 0.3).mean()),
    topK_weekly_periodic_pct=100 * float((obj_acf168 >= 0.3).mean()),
))
np.savez_compressed(os.path.join(OUT, 'wiki_arrays.npz'), hourly=hourly, hourly_bytes=hourly_bytes,
                    popularity=s[:2_000_000], days_active=np.bincount(days_active), M=M,
                    acf24=obj_acf24, acf168=obj_acf168, jacc=np.array(jacc))
json.dump(dict(summary=summary, per_day=per_day), open(os.path.join(OUT, 'wiki_summary.json'), 'w'), indent=1)
print('DONE', json.dumps(summary, indent=1))
