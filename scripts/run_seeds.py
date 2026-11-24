"""Robustness: repeat the main TS-GD runs with different random seeds (the model samples K cached objects at random).
Modes I and IT, 10% Wikipedia sample and Blue Coat B, all five cache sizes, horizon from results/cap_choice.json,
seeds 42 (the seed of all reported results, reused from sim_tsgd_capsel.jsonl) and 1, 2, 3, 4.
Writes results/sim_seeds.jsonl (resumable) and results/seeds_summary.md.  usage: run_seeds.py [parallel=4]"""
import json, os, subprocess, sys, statistics as st
from concurrent.futures import ThreadPoolExecutor, as_completed
TS = os.environ.get('TSGD_BIN', 'bin/tsgdsim'); PAR = int(sys.argv[1]) if len(sys.argv) > 1 else 4
P, R = 'data/processed/', 'results/'; OUT = R + 'sim_seeds.jsonl'
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]; MODES = ['I', 'IT']; SEEDS = [42, 1, 2, 3, 4]; TRACES = ['wiki_s10', 'bluecoat_B']
choice = json.load(open(R + 'cap_choice.json'))['choice']
load = lambda p: [json.loads(l) for l in open(p)] if os.path.exists(p) else []
done = {(d['trace'], d['mode'], d['cache_pct'], d['seed']) for d in load(OUT)}
for d in load(R + 'sim_tsgd_capsel.jsonl'):            # seed 42 = the reported runs
    k = (d['trace'], d['mode'], d['cache_pct'], 42)
    if d['mode'] in MODES and k not in done:
        d = dict(d); d['seed'] = 42; open(OUT, 'a').write(json.dumps(d) + '\n'); done.add(k)
meta = {t: json.load(open(P + t + '.bin.json')) for t in TRACES}
jobs = [(t, m, p, s) for t in TRACES for p in SIZES for m in MODES for s in SEEDS if (t, m, p, s) not in done]
print(len(jobs), 'runs to do', flush=True)
def run(j):
    t, m, p, s = j; mt = meta[t]
    out = subprocess.run([TS, P + t + '.bin', str(int(mt['working_set_bytes'] * p)), str(mt['test_start']), m], capture_output=True, text=True,
                         env={**os.environ, 'TSGD_CAP_HOURS': str(choice[str(p)]), 'TSGD_SEED': str(s)}).stdout
    d = json.loads(out); d.update(trace=t, cache_pct=p); return d
with ThreadPoolExecutor(PAR) as ex:
    for f in as_completed([ex.submit(run, j) for j in jobs]):
        d = f.result(); open(OUT, 'a').write(json.dumps(d) + '\n')
        print('%-10s %-3s seed=%-2d %4.1f%%  HR=%.4f  BHR=%.4f' % (d['trace'], d['mode'], d['seed'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio']), flush=True)
# ---- summary ----
D = {(d['trace'], d['mode'], d['cache_pct'], d['seed']): d for d in load(OUT)}
G = {(d['trace'], d['cache_pct']): d['hit_ratio'] for d in load(R + 'sim_baselines.jsonl') if d['alg'] == 'GDSF' and d.get('cost') == 'one'}
md = ['# TS-GD robustness over 5 random seeds (HR %, mean ± standard deviation [min–max])\n']
for t in TRACES:
    md += [f'\n## {t}\n', '| size | I | IT | IT − I (paired, mean ± sd) | IT − GDSF (min over seeds) |', '|---|---|---|---|---|']
    for p in SIZES:
        h = {m: [100 * D[(t, m, p, s)]['hit_ratio'] for s in SEEDS if (t, m, p, s) in D] for m in MODES}
        if any(len(v) < len(SEEDS) for v in h.values()): continue
        fmt = lambda v: f'{st.mean(v):.2f} ± {st.stdev(v):.2f} [{min(v):.2f}–{max(v):.2f}]'
        diff = [a - b for a, b in zip(h['IT'], h['I'])]
        g = 100 * G[(t, p)]
        md.append(f'| {100*p:g}% | {fmt(h["I"])} | {fmt(h["IT"])} | {st.mean(diff):+.2f} ± {st.stdev(diff):.2f} | {min(h["IT"]) - g:+.2f} |')
open(R + 'seeds_summary.md', 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
