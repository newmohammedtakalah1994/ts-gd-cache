"""Convert our binary trace to libCacheSim's oracleGeneral format:
record = uint32 timestamp, uint64 obj_id, uint32 obj_size, int64 next_access_vtime (-1 if none), packed (24 bytes).
Low-memory version (works for the full 207M-request Wikipedia trace on a 16 GB machine); writes <name>.part then renames,
and skips the work if the output already exists.  usage: python scripts/to_oracle_general.py data/processed/<trace>.bin"""
import os, sys, numpy as np
src = sys.argv[1]; dst = src.replace('.bin', '.oracleGeneral.bin')
if os.path.exists(dst): print('exists:', dst); sys.exit(0)
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
r = np.memmap(src, dtype=REC, mode='r'); n = len(r)
ids = np.array(r['id'])                                   # 4 bytes / request
o = np.argsort(ids, kind='stable')                         # requests grouped by object, in time order
sid = ids[o]; same = sid[1:] == sid[:-1]; del sid, ids
nxt = np.full(n, -1, np.int64); nxt[o[:-1][same]] = o[1:][same]; del o, same
OUT = np.dtype([('t', '<u4'), ('id', '<u8'), ('size', '<u4'), ('next', '<i8')], align=False)
CH = 10_000_000
with open(dst + '.part', 'wb') as f:
    for s in range(0, n, CH):
        e = min(n, s + CH); blk = np.empty(e - s, OUT); rr = r[s:e]
        blk['t'] = rr['t']; blk['id'] = rr['id'].astype(np.uint64) + 1; blk['size'] = rr['size']; blk['next'] = nxt[s:e]
        blk.tofile(f)
os.rename(dst + '.part', dst); print(dst, n, 'records,', OUT.itemsize, 'bytes each')
