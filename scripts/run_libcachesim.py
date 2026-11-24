"""Run libCacheSim's official implementations on our traces with our protocol (warm-up, cache sizes).
Resumable; appends to results/sim_libcachesim.jsonl.  usage: python scripts/run_libcachesim.py <cachesim_bin> <parallel> trace.bin ..."""
import sys, os, re, json, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed
BIN, PAR, traces = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
OUT = 'results/sim_libcachesim.jsonl'
ALGS = ['lru', 'gdsf', 'arc', 'wtinyLFU', 's3fifo', 'sieve', 's4fifo', 'beladySize', 'GLCache', 'lfuda', 'lrb']   # fast first, slow last
if os.environ.get('LCS_ALGS'): ALGS = os.environ['LCS_ALGS'].split(',')   # subset, e.g. for the full Wikipedia trace
TIMEOUT = {'bluecoat_B': 1800, 'wiki_s10': 3 * 3600, 'wiki_full': 8 * 3600}   # seconds per run; a run that exceeds it is recorded as a timeout
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]
if os.environ.get('LCS_SIZES'): SIZES = [float(x) for x in os.environ['LCS_SIZES'].split(',')]
done = set()
if os.path.exists(OUT):
    for l in open(OUT): d = json.loads(l); done.add((d['trace'], d['alg'], d['cache_pct']))
jobs = []
for tr in traces:
    meta = json.load(open(tr + '.json')); name = os.path.basename(tr).replace('.bin', '')
    for a in ALGS:
        for p in SIZES:
            if (name, a, p) not in done: jobs.append((tr.replace('.bin', '.oracleGeneral.bin'), name, a, p, int(meta['working_set_bytes'] * p), meta['test_start']))
print(len(jobs), 'runs to do', flush=True)
pat = re.compile(r'(\d+) req, miss ratio ([\d.]+)(?:, byte miss ratio ([\d.]+))?.*throughput ([\d.]+) MQPS')
def run(j):
    tr, name, a, p, cap, warm = j; t0 = time.time()
    d = dict(trace=name, alg=a, cache_pct=p, cache_bytes=cap)
    try:
        cmd = [BIN, tr, 'oracleGeneral', a, str(cap), '--warmup-sec', str(warm), '--num-thread', '1']
        if sys.platform == 'darwin' and os.path.exists('/usr/bin/time'): cmd = ['/usr/bin/time', '-l'] + cmd
        pr = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT.get(name, 3600))
    except subprocess.TimeoutExpired:
        d.update(error='timeout after %d s' % TIMEOUT.get(name, 3600), wall_seconds=round(time.time() - t0, 1)); return d
    m = pat.search(pr.stdout); d['wall_seconds'] = round(time.time() - t0, 1)
    mm = re.search(r'(\d+)\s+maximum resident set size', pr.stderr)
    if mm: d['max_rss_gb'] = round(int(mm.group(1)) / 2**30, 2)   # bytes on macOS
    if pr.returncode != 0 and not m: d['returncode'] = pr.returncode
    if m: d.update(requests=int(m.group(1)), hit_ratio=1 - float(m.group(2)), byte_hit_ratio=1 - float(m.group(3)) if m.group(3) else None, throughput_mqps=float(m.group(4)))
    else: d.update(error=(pr.stdout + pr.stderr)[-400:])
    return d
# order jobs: Blue Coat first, and within a trace the fast algorithms first
jobs.sort(key=lambda j: (j[1] != 'bluecoat_B', ALGS.index(j[2]), j[3]))
if os.environ.get('LCS_SIZES'): jobs.sort(key=lambda j: (SIZES.index(j[3]), ALGS.index(j[2])))   # size by size: partial results stay usable
with ThreadPoolExecutor(PAR) as ex:
    for fut in as_completed([ex.submit(run, j) for j in jobs]):   # print/save each result as soon as it finishes
        d = fut.result()
        open(OUT, 'a').write(json.dumps(d) + '\n')
        if 'error' in d: print('%-12s %-10s %5.1f%%  ERROR: %s' % (d['trace'], d['alg'], 100 * d['cache_pct'], d['error'][-150:].replace('\n', ' ')), flush=True)
        else: print('%-12s %-10s %5.1f%%  HR=%.4f  BHR=%.4f  %.2f MQPS' % (d['trace'], d['alg'], 100 * d['cache_pct'], d['hit_ratio'], d['byte_hit_ratio'] or -1, d['throughput_mqps']), flush=True)
print('ALL DONE')
