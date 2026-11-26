"""Full Wikipedia trace: TS-GD (IT) and our GDSF / Belady-Size against the libCacheSim policies run on the full trace.
Reads results/ (or 05_results/)sim_fullscale.jsonl, sim_fullscale_capsel.jsonl and sim_libcachesim.jsonl; writes libcachesim_full.md there."""
import json, os
R = '05_results' if os.path.isdir('05_results') else 'results'
SIZES = [0.001, 0.005, 0.01, 0.05, 0.10]
def rows(f): return [json.loads(l) for l in open(os.path.join(R, f)) if l.strip()]
res = {}
for r in rows('sim_fullscale.jsonl'):
    if r.get('name') in ('GDSF', 'BELADYSIZE', 'LFUDA'): res[(r['name'], r['cache_pct'])] = r
for r in rows('sim_fullscale_capsel.jsonl'):
    if (r.get('mode') or r.get('name')) == 'IT': res[('TS-GD', r['cache_pct'])] = r   # horizon chosen on warm-up data
lcs = {'gdsf': 'GDSF (libCacheSim)', 's3fifo': 'S3-FIFO', 'sieve': 'SIEVE', 'GLCache': 'GL-Cache', 'lrb': 'LRB'}
for r in rows('sim_libcachesim.jsonl'):
    if r.get('trace') == 'wiki_full' and r.get('alg') in lcs and 'hit_ratio' in r: res[(lcs[r['alg']], r['cache_pct'])] = r
order = ['TS-GD', 'GDSF', 'LFUDA'] + list(lcs.values()) + ['BELADYSIZE']
label = {'TS-GD': 'TS-GD (IT)', 'GDSF': 'GDSF (our simulator)', 'LFUDA': 'LFU-DA (our simulator)', 'BELADYSIZE': 'Belady-Size (offline bound)'}
md = ['# Full Wikipedia trace (207.6 M requests; test days 14-20, 62.4 M requests): TS-GD against libCacheSim', '']
for key, title in (('hit_ratio', 'Hit ratio %'), ('byte_hit_ratio', 'Byte hit ratio %')):
    md += ['## ' + title, '', '| Policy | ' + ' | '.join('%g%%' % (100 * p) for p in SIZES) + ' |', '|---' * 6 + '|']
    online = [n for n in order if n != 'BELADYSIZE']
    best = {p: max(res[(n, p)][key] for n in online if (n, p) in res) for p in SIZES}
    for n in order:
        cells = []
        for p in SIZES:
            r = res.get((n, p)); v = None if r is None else r[key]
            cells.append('—' if v is None else ('**%.1f**' % (100 * v) if n != 'BELADYSIZE' and v == best[p] else '%.1f' % (100 * v)))
        md.append('| %s | %s |' % (label.get(n, n), ' | '.join(cells)))
    md.append('')
md += ['## Wall-clock time of the libCacheSim runs (hours; Windows laptop, WSL2, one run at a time)', '',
       '| Policy | ' + ' | '.join('%g%%' % (100 * p) for p in SIZES) + ' |', '|---' * 6 + '|']
for n in lcs.values():
    md.append('| %s | %s |' % (n, ' | '.join('%.2f' % (res[(n, p)]['wall_seconds'] / 3600) for p in SIZES)))
md += ['', 'Wall time includes reading the 4.7 GB trace from the Windows file system, which dominates the time of the fast policies.',
       'Hit ratios do not depend on the machine; times measured on different machines must not be compared directly.']
open(os.path.join(R, 'libcachesim_full.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
