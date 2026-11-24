"""Run the baseline grid (resumable). Results appended to results/sim_baselines.jsonl.
usage: python3 scripts/run_baselines.py <trace.bin> [time_budget_seconds] [parallel]"""
import sys, os, json, time, subprocess, numpy as np
trace = sys.argv[1]; budget = float(sys.argv[2]) if len(sys.argv) > 2 else 150; par = int(sys.argv[3]) if len(sys.argv) > 3 else 3
meta = json.load(open(trace + '.json')); name = os.path.basename(trace).replace('.bin', '')
OUT = 'results/sim_baselines.jsonl'
if 'working_set_bytes' not in meta:   # unique bytes requested in the test window
    r = np.fromfile(trace, dtype=[('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
    m = r['t'] >= meta['test_start']; ids, sz = r['id'][m], r['size'][m].astype(np.int64)
    mx = np.zeros(int(ids.max()) + 1, np.int64); np.maximum.at(mx, ids, sz)
    meta['working_set_bytes'] = int(mx.sum()); meta['test_requests'] = int(m.sum())
    json.dump(meta, open(trace + '.json', 'w'), indent=1)
WS = meta['working_set_bytes']
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]
GRID = [(a, c) for a in ['LRU', 'LFUDA', 'GDS', 'GDSF', 'GDSTAR', 'BELADY', 'BELADYSIZE', 'KMGDSF', 'DMCM'] for c in ['one', 'latency']
        if not (c == 'latency' and a in ('LRU', 'LFUDA', 'BELADY', 'BELADYSIZE', 'KMGDSF', 'DMCM'))]
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        d = json.loads(l); done.add((d['trace'], d['alg'], d['cost'], d['cache_pct']))
todo = [(a, c, p) for p in SIZES for a, c in GRID if (name, a, c, p) not in done]
start = time.time(); running = []
def collect(block=False):
    for pr in list(running):
        if block or pr[0].poll() is not None:
            out = pr[0].communicate()[0]; d = json.loads(out.strip().splitlines()[-1])
            d.update(trace=name, cache_pct=pr[1][2]); open(OUT, 'a').write(json.dumps(d) + '\n'); running.remove(pr)
            print(name, d['alg'], d['cost'], d['cache_pct'], 'HR=%.4f BHR=%.4f' % (d['hit_ratio'], d['byte_hit_ratio']), flush=True)
while todo and time.time() - start < budget:
    while len(running) >= par: collect(); time.sleep(0.2)
    a, c, p = todo.pop(0)
    cmd = ['bin/cachesim', trace, a, str(int(WS * p)), str(meta['test_start']), c]
    WFILE = {'KMGDSF': trace.replace('.bin', '_kmeans.w'), 'DMCM': trace.replace('.bin', '_knn.w')}
    if a in WFILE:
        if not os.path.exists(WFILE[a]): continue
        cmd += ['2', WFILE[a]]
    running.append((subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True), (a, c, p)))
collect(block=True)
print('remaining', len(todo))
