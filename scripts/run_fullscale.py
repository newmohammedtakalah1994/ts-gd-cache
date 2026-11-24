"""Full-scale runs on wiki_full.bin (run on the Mac). Resumable; results in results/sim_fullscale.jsonl.
Memory: each process holds the whole trace (~3.3 GB) + per-object state, so at most 2 run in parallel on 16 GB."""
import os, sys, json, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
TR = 'data/processed/wiki_full.bin'; m = json.load(open(TR + '.json')); OUT = 'results/sim_fullscale.jsonl'
CS, TS = os.environ.get('CS_BIN', 'bin/cachesim'), os.environ.get('TSGD_BIN', 'bin/tsgdsim'); PAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]
jobs = [('cachesim', a, p) for p in SIZES for a in ['GDSF', 'GDSFA', 'LFUDA', 'LRU', 'GDSTAR', 'BELADYSIZE']] + \
       [('tsgd', mo, p) for p in SIZES for mo in ['I', 'IT', 'ITC', 'ITG']]
done = {(d['kind'], d['name'], d['cache_pct']) for d in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
def run(j):
    kind, name, p = j; cap = str(int(m['working_set_bytes'] * p)); ts = str(m['test_start'])
    cmd = [CS, TR, name, cap, ts, 'one'] if kind == 'cachesim' else [TS, TR, cap, ts, name]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout); d.update(kind=kind, name=name, trace='wiki_full', cache_pct=p); return d
todo = [j for j in jobs if j not in done]; print(len(todo), 'runs to do', flush=True)
with ThreadPoolExecutor(PAR) as ex:
    for f in as_completed([ex.submit(run, j) for j in todo]):
        d = f.result(); open(OUT, 'a').write(json.dumps(d) + '\n')
        print('%-8s %-10s %5.1f%%  HR=%.4f  BHR=%.4f  (%.0fs)' % (d['kind'], d['name'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio'], d['sim_seconds']), flush=True)
print('FULLSCALE DONE')
