"""Tables + figures for the baseline results."""
import json, collections, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
rows = [json.loads(l) for l in open('results/sim_baselines.jsonl')]
best = {}
for r in rows: best[(r['trace'], r['alg'], r['cost'], r['cache_pct'])] = r
ALGS = ['LRU', 'LFUDA', 'GDS', 'GDSF', 'GDSTAR', 'KMGDSF', 'DMCM', 'BELADY', 'BELADYSIZE']
COL = {'LRU': '#2a78d6', 'LFUDA': '#eb6834', 'GDS': '#1baf7a', 'GDSF': '#eda100', 'GDSTAR': '#e87ba4', 'KMGDSF': '#6250d6', 'DMCM': '#e34948', 'BELADY': '#52514e', 'BELADYSIZE': '#0b0b0b'}
md = []
for tr, title in [('wiki_s10', 'Wikipedia 2019 (10% object sample), test = days 14-20'), ('bluecoat_B', 'Blue Coat proxy B, test = 3-6 May 2005')]:
    sizes = sorted({k[3] for k in best if k[0] == tr})
    for metric in ['hit_ratio', 'byte_hit_ratio']:
        md.append(f'\n### {title} — {metric} (cost C=1)\n\n| Policy | ' + ' | '.join(f'{100*s:g}%' for s in sizes) + ' |\n|---|' + '---|' * len(sizes))
        for a in ALGS:
            md.append(f'| {a} | ' + ' | '.join(f"{100*best[(tr,a,'one',s)][metric]:.1f}" if (tr,a,'one',s) in best else '-' for s in sizes) + ' |')
    md.append(f'\nLatency-cost variant (C = recorded latency), hit ratio:\n\n| Policy | ' + ' | '.join(f'{100*s:g}%' for s in sizes) + ' |\n|---|' + '---|' * len(sizes))
    for a in ['GDS', 'GDSF', 'GDSTAR']:
        md.append(f'| {a} | ' + ' | '.join(f"{100*best[(tr,a,'latency',s)]['hit_ratio']:.1f}" for s in sizes) + ' |')
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, metric, lab in zip(axs, ['hit_ratio', 'byte_hit_ratio'], ['Hit ratio (%)', 'Byte hit ratio (%)']):
        for a in ALGS:
            ys = [100 * best[(tr, a, 'one', s)][metric] for s in sizes]
            ax.plot([100 * s for s in sizes], ys, marker='o', ms=4, color=COL[a], label=a,
                    linestyle='--' if a.startswith('BELADY') else '-')
        ax.set_xscale('log'); ax.set_xlabel('Cache size (% of test-week unique bytes)'); ax.set_ylabel(lab)
        ax.grid(True, color='#e4e3df'); ax.spines[['top', 'right']].set_visible(False)
    axs[0].legend(frameon=False, fontsize=8); fig.suptitle(title, x=0.01, ha='left', fontsize=10)
    fig.tight_layout(); fig.savefig(f'results/figures/fig6_baselines_{tr}.png', dpi=150); plt.close()
open('results/baselines_tables.md', 'w').write('# Baseline results\n' + '\n'.join(md) + '\n')
print('\n'.join(md))
