"""Appendix: sensitivity of TS-GD (IT) to the sample size K and to the prediction horizon CAP, on the 10% Wikipedia sample.
Writes results/sim_sensitivity.jsonl (resumable). usage: run_sensitivity.py [parallel=4]"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
TS = os.environ.get('TSGD_BIN', 'bin/tsgdsim'); PAR = int(sys.argv[1]) if len(sys.argv) > 1 else 4
TRACE = 'data/processed/wiki_s10.bin'; OUT = 'results/sim_sensitivity.jsonl'
m = json.load(open(TRACE + '.json'))
jobs = [('K', K, 24, p) for p in (0.01, 0.05) for K in (16, 32, 64, 128, 256)] + \
       [('CAP', 64, c, p) for p in (0.01, 0.05, 0.10) for c in (6, 12, 24, 48, 72)]
key = lambda j: (j[1], j[2], j[3])
done = {(d['K'], d['cap_hours'], d['cache_pct']) for d in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
todo = []; seen = set()
for j in jobs:
    if key(j) in done or key(j) in seen: continue
    seen.add(key(j)); todo.append(j)
print(len(todo), 'runs to do', flush=True)
def run(j):
    _, K, c, p = j
    cmd = [TS, TRACE, str(int(m['working_set_bytes'] * p)), str(m['test_start']), 'IT', str(K)]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, 'TSGD_CAP_HOURS': str(c)}).stdout)
    d.update(trace='wiki_s10', cache_pct=p); return d
with ThreadPoolExecutor(PAR) as ex, open(OUT, 'a') as out:
    for f in as_completed([ex.submit(run, j) for j in todo]):
        d = f.result(); out.write(json.dumps(d) + '\n'); out.flush()
        print('K=%-4d CAP=%2gh %4.1f%%  HR=%.4f  BHR=%.4f  %.1f us/req' % (d['K'], d['cap_hours'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio'], d['us_per_request']), flush=True)
