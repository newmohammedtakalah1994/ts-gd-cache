"""Option 2, full Wikipedia trace: TS-GD variants with the prediction horizon chosen on warm-up data (results/cap_choice.json).
Runs already done with the same horizon by the current simulator are reused (CAP = 24 h: results/sim_fullscale.jsonl,
IT with CAP = 72 h: results/sim_fullscale_cap.jsonl). Resumable; writes results/sim_fullscale_capsel.jsonl.
usage: run_fullscale_capsel.py [parallel=2]"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
TS = os.environ.get('TSGD_BIN', 'bin/tsgdsim'); PAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2
R = 'results/'; TRACE = 'data/processed/wiki_full.bin'; OUT = R + 'sim_fullscale_capsel.jsonl'
m = json.load(open(TRACE + '.json')); choice = json.load(open(R + 'cap_choice.json'))['choice']
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]; MODES = ['I', 'IT', 'ITC', 'ITG']
load = lambda p: [json.loads(l) for l in open(p)] if os.path.exists(p) else []
reuse = {}
for d in load(R + 'sim_fullscale.jsonl'):
    if d.get('alg') == 'TSGD': reuse[(d['mode'], d['cache_pct'], 24)] = d
for d in load(R + 'sim_fullscale_cap.jsonl'): reuse[(d['mode'], d['cache_pct'], d['cap_hours'])] = d
done = {(d['mode'], d['cache_pct']) for d in load(OUT)}
jobs = []
for p in SIZES:
    c = choice[str(p)]
    for mo in MODES:
        if (mo, p) in done: continue
        if (mo, p, c) in reuse:
            d = dict(reuse[(mo, p, c)]); d.update(cap_hours=c, trace='wiki_full', cache_pct=p, reused=True); open(OUT, 'a').write(json.dumps(d) + '\n'); continue
        jobs.append((mo, p, c))
print(len(jobs), 'full-trace runs to do', flush=True)
def run(j):
    mo, p, c = j
    d = json.loads(subprocess.run([TS, TRACE, str(int(m['working_set_bytes'] * p)), str(m['test_start']), mo], capture_output=True, text=True,
                                  env={**os.environ, 'TSGD_CAP_HOURS': str(c)}).stdout)
    d.update(trace='wiki_full', cache_pct=p); return d
with ThreadPoolExecutor(PAR) as ex:
    for f in as_completed([ex.submit(run, j) for j in jobs]):
        d = f.result(); open(OUT, 'a').write(json.dumps(d) + '\n')
        print('tsgd %-4s CAP=%3gh %4.1f%%  HR=%.4f  BHR=%.4f  (%.0fs)' % (d['mode'], d['cap_hours'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio'], d['sim_seconds']), flush=True)
print('DONE')
