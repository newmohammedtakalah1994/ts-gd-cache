"""Cross-check the C++ simulator against straightforward Python reference implementations (LRU, GDSF)."""
import numpy as np, subprocess, json, heapq, collections
REC = [('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')]
r = np.fromfile('data/processed/bluecoat_B.bin', dtype=REC)[:300000]
r.tofile('/tmp/small.bin'); test_start = int(r['t'][150000]); cap = int(r['size'][:].astype(np.int64).sum() * 0.002)
def ref(alg):
    inc, used, L, hits, req = {}, 0, 0.0, 0, 0
    lru = collections.OrderedDict(); heap = []; ver = {}; freq = {}
    for i, (t, oid, sz, c) in enumerate(r):
        oid, sz = int(oid), int(sz); meas = t >= test_start; req += meas
        if oid in inc:
            hits += meas
            if sz != inc[oid]: used += sz - inc[oid]; inc[oid] = sz
            freq[oid] += 1
        else:
            if sz > cap or sz == 0: continue
            while used + sz > cap:
                if alg == 'LRU': v, _ = lru.popitem(last=False)
                else:
                    while True:
                        k, v, vv = heapq.heappop(heap)
                        if v in inc and ver[v] == vv: break
                    L = k
                used -= inc.pop(v)
            inc[oid] = sz; used += sz; freq[oid] = 1
        if alg == 'LRU': lru[oid] = 1; lru.move_to_end(oid)
        else: ver[oid] = ver.get(oid, 0) + 1; heapq.heappush(heap, (L + freq[oid] / max(1, inc[oid]), oid, ver[oid]))
    return hits / req
for alg in ['LRU', 'GDSF']:
    out = json.loads(subprocess.run(['bin/cachesim', '/tmp/small.bin', alg, str(cap), str(test_start), 'one'], capture_output=True, text=True).stdout)
    print(alg, 'C++ HR=%.6f' % out['hit_ratio'], 'Python HR=%.6f' % ref(alg))
