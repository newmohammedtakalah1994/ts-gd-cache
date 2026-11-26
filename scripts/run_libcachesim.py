"""Run libCacheSim's official implementations on our traces with our protocol (warm-up, cache sizes).
Resumable; appends to results/sim_libcachesim.jsonl.  usage: python scripts/run_libcachesim.py <cachesim_bin> <parallel> trace.bin ..."""
import sys, os, re, json, subprocess, time, signal, threading
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
    """Run one simulation. The simulator's output is read while it runs and only its last 2,000 characters
    are kept, so memory use stays small even when libCacheSim prints a very large log."""
    tr, name, a, p, cap, warm = j; t0 = time.time(); limit = TIMEOUT.get(name, 3600)
    d = dict(trace=name, alg=a, cache_pct=p, cache_bytes=cap)
    cmd = [BIN, tr, 'oracleGeneral', a, str(cap), '--warmup-sec', str(warm), '--num-thread', '1']
    if sys.platform == 'darwin' and os.path.exists('/usr/bin/time'): cmd = ['/usr/bin/time', '-l'] + cmd   # macOS: peak memory in bytes
    elif os.path.exists('/usr/bin/time'): cmd = ['/usr/bin/time', '-v'] + cmd                              # Linux / WSL: peak memory in kB
    st = {'match': None, 'rss': None, 'stdout': '', 'stderr': ''}
    def consume(stream, kind):   # read line by line; keep only a short tail and the parsed values
        try:
            for chunk in iter(lambda: stream.readline(65536), ''):
                st[kind] = (st[kind] + chunk)[-2000:]
                if kind == 'stdout':
                    m = pat.search(chunk)
                    if m: st['match'] = m.groups()   # the final summary is the last match
                else:
                    mm = re.search(r'(\d+)\s+maximum resident set size', chunk)
                    if mm: st['rss'] = round(int(mm.group(1)) / 2**30, 2)
                    ml = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', chunk)
                    if ml: st['rss'] = round(int(ml.group(1)) / 2**20, 2)
        finally:
            stream.close()
    print('START %s %s cache=%g%%' % (name, a, 100 * p), flush=True)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', start_new_session=True)
    except OSError as e:
        d['error'] = str(e); return d
    readers = [threading.Thread(target=consume, args=(proc.stdout, 'stdout')), threading.Thread(target=consume, args=(proc.stderr, 'stderr'))]
    for t in readers: t.start()
    timed_out = False
    try:
        proc.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        try: os.killpg(proc.pid, signal.SIGKILL)   # kill the simulator and its /usr/bin/time wrapper
        except ProcessLookupError: pass
        proc.wait()
    for t in readers: t.join()
    d['wall_seconds'] = round(time.time() - t0, 1)
    if st['rss'] is not None: d['max_rss_gb'] = st['rss']   # GiB
    if timed_out:
        d['error'] = 'timeout after %d s' % limit; return d
    if proc.returncode != 0:
        d['returncode'] = proc.returncode
        if proc.returncode in (-9, 137): d['killed'] = 'SIGKILL (possibly out of memory)'
        d['error'] = 'exit code %d: %s' % (proc.returncode, st['stderr'][-400:]); return d
    m = st['match']
    if m: d.update(requests=int(m[0]), hit_ratio=1 - float(m[1]), byte_hit_ratio=1 - float(m[2]) if m[2] else None, throughput_mqps=float(m[3]))
    else: d['error'] = 'no summary line found: ' + (st['stdout'] + st['stderr'])[-400:]
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
