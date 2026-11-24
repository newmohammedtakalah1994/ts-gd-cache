"""Build compact binary traces for the C++ simulator.
Record = (uint32 t_seconds, uint32 dense_obj_id, uint32 size_bytes, float32 cost_seconds), little-endian, time-ordered.
Wikipedia: spatial sampling by object hash (keeps an object's full request history; SHARDS-style), rate = SAMPLE %.
Blue Coat: proxy B (files 002+003), cacheable GET requests only, no sampling."""
import sys, os, glob, json, numpy as np, pandas as pd
which = sys.argv[1]; OUTD = 'data/processed'
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])

def write(path, t, ids, size, cost, meta):
    _, dense = np.unique(ids, return_inverse=True)
    r = np.empty(len(t), REC); r['t'] = t; r['id'] = dense; r['size'] = np.minimum(size, 2**32 - 1); r['cost'] = cost
    r.tofile(path); meta.update(requests=int(len(r)), objects=int(dense.max() + 1)); json.dump(meta, open(path + '.json', 'w'), indent=1)
    print(meta)

if which == 'wiki':
    SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    T, I, S, C = [], [], [], []
    for f in sorted(glob.glob('data/wikipedia_text/cache-t-*.gz')):
        df = pd.read_csv(f, sep='\t', header=0, names=['t', 'id', 'size', 'tfb'],
                         dtype={'t': np.uint32, 'id': np.int32, 'size': np.int64, 'tfb': np.float32})
        h = (df.id.values.astype(np.uint32).astype(np.uint64) * np.uint64(2654435761)) & np.uint64(0xFFFFFFFF)
        m = (h % np.uint64(100)) < SAMPLE
        T.append(df.t.values[m]); I.append(df.id.values[m]); S.append(df['size'].values[m]); C.append(df.tfb.values[m])
        print(f, int(m.sum()), flush=True)
    t = np.concatenate(T); o = np.argsort(t, kind='stable')
    write(f'{OUTD}/wiki_s{SAMPLE}.bin', t[o], np.concatenate(I)[o], np.concatenate(S)[o], np.concatenate(C)[o],
          dict(source='Wikipedia CDN text 2019', sample_pct=SAMPLE, warmup_end=14 * 86400, test_start=14 * 86400))
else:
    import numpy as np
    parts = []
    for i in ['002', '003']:
        z = np.load(f'{OUTD}/bluecoat_{i}.npz'); a = z['actions'][z['act']].astype(str)
        nc = (np.char.find(a, 'NC_') >= 0) | (np.char.find(a, 'ERR') >= 0) | (np.char.find(a, 'DENIED') >= 0)
        keep = z['get'] & np.isin(z['status'], [200, 203, 206, 300, 301, 304]) & ~nc
        parts.append((z['ts'][keep], z['obj'][keep], z['size'][keep], z['taken'][keep] / 1000.0))
    t = np.concatenate([p[0] for p in parts]); o = np.argsort(t, kind='stable')
    t0 = np.datetime64('2005-04-28T00:00', 's').astype(np.int64)
    t = t[o]; keep = t >= t0
    ids = np.concatenate([p[1] for p in parts])[o][keep]; size = np.concatenate([p[2] for p in parts])[o][keep]
    cost = np.concatenate([p[3] for p in parts])[o][keep]
    # 304 responses carry ~no body: use the object's largest observed size as its size
    s = pd.Series(size).groupby(ids).transform('max').values
    write(f'{OUTD}/bluecoat_B.bin', (t[keep] - t0).astype(np.uint32), ids, s, cost.astype(np.float32),
          dict(source='Blue Coat proxy B (002+003), cacheable GET', t0='2005-04-28T00:00Z',
               warmup_end=5 * 86400, test_start=5 * 86400))
