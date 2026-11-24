"""Full-scale (100%) Wikipedia trace for the simulators, built day by day (memory-safe).
Pass 1: collect the distinct object ids (per-day uniques, then a global unique). Pass 2: write records with dense ids.
Output: data/processed/wiki_full.bin (+ .json with warm-up/test split and the test-week working set)."""
import glob, json, numpy as np, pandas as pd
files = sorted(glob.glob('data/wikipedia_text/cache-t-*.gz')); OUT = 'data/processed/wiki_full.bin'
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
def load(f):
    return pd.read_csv(f, sep='\t', header=0, names=['t', 'id', 'size', 'tfb'],
                       dtype={'t': np.uint32, 'id': np.int32, 'size': np.int64, 'tfb': np.float32})
uq = []
for f in files:
    uq.append(np.unique(load(f).id.values)); print('pass1', f, flush=True)
uniq = np.unique(np.concatenate(uq)); del uq
print('distinct objects', len(uniq), flush=True)
TEST = 14 * 86400; wsmax = np.zeros(len(uniq), np.int64); n = 0; last_t = 0
with open(OUT, 'wb') as fo:
    for f in files:
        df = load(f)
        if not (np.diff(df.t.values.astype(np.int64)) >= 0).all(): df = df.sort_values('t', kind='stable')
        assert int(df.t.values[0]) >= last_t, 'files are not consecutive in time'
        r = np.empty(len(df), REC); r['t'] = df.t.values; r['id'] = np.searchsorted(uniq, df.id.values)
        r['size'] = np.minimum(df['size'].values, 2**32 - 1); r['cost'] = df.tfb.values
        m = r['t'] >= TEST
        if m.any(): np.maximum.at(wsmax, r['id'][m], r['size'][m].astype(np.int64))
        r.tofile(fo); n += len(r); last_t = int(r['t'][-1]); print('pass2', f, len(r), flush=True)
meta = dict(source='Wikipedia CDN text 2019 (full, 100%)', sample_pct=100, warmup_end=TEST, test_start=TEST,
            requests=int(n), objects=int(len(uniq)), working_set_bytes=int(wsmax.sum()))
json.dump(meta, open(OUT + '.json', 'w'), indent=1); print(meta)
