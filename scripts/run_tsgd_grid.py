"""Full TS-GD experiment grid (resumable). Appends to results/sim_tsgd.jsonl.
usage: python scripts/run_tsgd_grid.py <parallel_jobs> trace1.bin [trace2.bin ...]"""
import sys, os, json, subprocess
from concurrent.futures import ThreadPoolExecutor
par = int(sys.argv[1]); traces = sys.argv[2:]; OUT = 'results/sim_tsgd.jsonl'
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]; MODES = ['I', 'IT', 'ITC', 'IG', 'ITG']
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        d = json.loads(l); done.add((d['trace'], d['mode'], d['cache_pct'], d['K'], d['k']))
jobs = []
for tr in traces:
    meta = json.load(open(tr + '.json')); name = os.path.basename(tr).replace('.bin', '')
    for p in SIZES:
        for m in MODES:
            if (name, m, p, 64, 8) not in done:
                jobs.append((tr, name, m, p, int(meta['working_set_bytes'] * p), meta['test_start']))
print(len(jobs), 'runs to do', flush=True)
def run(j):
    tr, name, m, p, cap, ts = j
    out = subprocess.run([os.environ.get('TSGD_BIN', 'bin/tsgdsim'), tr, str(cap), str(ts), m], capture_output=True, text=True).stdout
    d = json.loads(out); d.update(trace=name, cache_pct=p); return d
with ThreadPoolExecutor(par) as ex:
    for d in ex.map(run, jobs):
        open(OUT, 'a').write(json.dumps(d) + '\n')
        print('%-12s %-4s %5.1f%%  HR=%.4f  BHR=%.4f  (%.0fs)' % (d['trace'], d['mode'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio'], d['sim_seconds']), flush=True)
print('ALL DONE')
