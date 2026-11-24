"""Option 2: choose the prediction horizon CAP on WARM-UP data only, then re-run the main TS-GD experiments.
 1) validation trace: Wikipedia 10% sample, days 0-9 as warm-up, days 10-13 as validation (the test week, days 14-20, is never read)
 2) grid CAP in {24, 48, 72, 120} h for TS-GD (IT) at each cache size (as % of the validation working set) -> results/cap_validation.jsonl
 3) rule: for each cache size the CAP with the highest validation hit ratio (a CAP must beat a shorter one by > 0.05 points)
    -> results/cap_choice.json. The same size rule is applied to Blue Coat (its warm-up, 0.56M requests, is too short to tune on)
 4) main experiments on the test week with the chosen CAP: modes I, IT, ITC, IG, ITG on wiki_s10 and bluecoat_B -> results/sim_tsgd_capsel.jsonl
    (all runs are repeated with the current simulator, so every number in the new tables comes from one binary)
Resumable.  usage: python scripts/select_cap.py [parallel=4]"""
import json, os, subprocess, sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
TS = os.environ.get('TSGD_BIN', 'bin/tsgdsim'); PAR = int(sys.argv[1]) if len(sys.argv) > 1 else 4
P = 'data/processed/'; R = 'results/'
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]; CAPS = [24, 48, 72, 120]; MODES = ['I', 'IT', 'ITC', 'IG', 'ITG']
REC = np.dtype([('t', '<u4'), ('id', '<u4'), ('size', '<u4'), ('cost', '<f4')])
DAY = 86400

def tsgd(trace, cap_bytes, test_start, mode, cap_h):
    out = subprocess.run([TS, trace, str(int(cap_bytes)), str(test_start), mode], capture_output=True, text=True,
                         env={**os.environ, 'TSGD_CAP_HOURS': str(cap_h)}).stdout
    return json.loads(out)

def load(path): return [json.loads(l) for l in open(path)] if os.path.exists(path) else []

# ---- 1) validation trace (days 0-13 of the sample; validation = days 10-13) ----
VAL = P + 'wiki_s10_val.bin'
if not os.path.exists(VAL + '.json'):
    r = np.memmap(P + 'wiki_s10.bin', dtype=REC, mode='r'); keep = r['t'] < 14 * DAY; v = np.array(r[keep])
    w = v[v['t'] >= 10 * DAY]; ids, inv = np.unique(w['id'], return_inverse=True); mx = np.zeros(len(ids), np.uint64); np.maximum.at(mx, inv, w['size'].astype(np.uint64))
    v.tofile(VAL + '.part'); os.rename(VAL + '.part', VAL)
    json.dump(dict(source='Wikipedia 10% sample, days 0-13 only (validation = days 10-13)', test_start=10 * DAY, requests=int(len(v)),
                   validation_requests=int(len(w)), working_set_bytes=int(mx.sum())), open(VAL + '.json', 'w'), indent=1)
    print('validation trace:', len(v), 'requests,', len(w), 'in days 10-13', flush=True)
vm = json.load(open(VAL + '.json'))

# ---- 2) validation grid ----
OUTV = R + 'cap_validation.jsonl'
done = {(d['cap_hours'], d['cache_pct']) for d in load(OUTV)}
jobs = [(c, p) for p in SIZES for c in CAPS if (c, p) not in done]
print(len(jobs), 'validation runs to do', flush=True)
with ThreadPoolExecutor(PAR) as ex:
    futs = {ex.submit(tsgd, VAL, vm['working_set_bytes'] * p, vm['test_start'], 'IT', c): (c, p) for c, p in jobs}
    for f in as_completed(futs):
        c, p = futs[f]; d = f.result(); d.update(trace='wiki_s10_val', cache_pct=p); open(OUTV, 'a').write(json.dumps(d) + '\n')
        print('validation CAP=%3dh %4.1f%%  HR=%.4f  BHR=%.4f' % (c, 100 * p, d['hit_ratio'], d['byte_hit_ratio']), flush=True)

# ---- 3) choice ----
V = {(d['cap_hours'], d['cache_pct']): d['hit_ratio'] for d in load(OUTV)}
choice = {}
for p in SIZES:
    best = CAPS[0]
    for c in CAPS[1:]:
        if V[(c, p)] > V[(best, p)] + 0.0005: best = c
    choice[str(p)] = best
json.dump(dict(rule='per cache size: CAP with the highest validation HR (days 10-13 of the 10% sample); longer CAP only if > +0.05 points',
               validation_hr={str(p): {str(c): round(100 * V[(c, p)], 2) for c in CAPS} for p in SIZES}, choice=choice),
          open(R + 'cap_choice.json', 'w'), indent=1)
print('chosen CAP (hours) by cache size:', choice, flush=True)

# ---- 4) main experiments with the chosen CAP ----
OUT = R + 'sim_tsgd_capsel.jsonl'
done = {(d['trace'], d['mode'], d['cache_pct']) for d in load(OUT)}
jobs = []
for name in ['wiki_s10', 'bluecoat_B']:
    m = json.load(open(P + name + '.bin.json'))
    for p in SIZES:
        for mo in MODES:
            if (name, mo, p) in done: continue
            jobs.append((name, m, p, mo, choice[str(p)]))
print(len(jobs), 'test-week runs to do', flush=True)
def run(j):
    name, m, p, mo, c = j; d = tsgd(P + name + '.bin', m['working_set_bytes'] * p, m['test_start'], mo, c); d.update(trace=name, cache_pct=p); return d
with ThreadPoolExecutor(PAR) as ex:
    for f in as_completed([ex.submit(run, j) for j in jobs]):
        d = f.result(); open(OUT, 'a').write(json.dumps(d) + '\n')
        print('%-11s %-4s CAP=%3gh %4.1f%%  HR=%.4f  BHR=%.4f' % (d['trace'], d['mode'], d['cap_hours'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio']), flush=True)
print('DONE')
