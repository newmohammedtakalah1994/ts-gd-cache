"""Main comparison: all baselines + TS-GD variants. Writes results/main_results.md and figures fig7/fig8."""
import json, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
R = {}
for l in open('results/sim_baselines.jsonl'):
    d = json.loads(l)
    if d['cost'] == 'one': R[(d['trace'], d['alg'], d['cache_pct'])] = d
import os
# TS-GD with the prediction horizon chosen on warm-up data (option 2); the older 24-hour runs are kept in sim_tsgd.jsonl
TSF = 'results/sim_tsgd_capsel.jsonl' if os.path.exists('results/sim_tsgd_capsel.jsonl') else 'results/sim_tsgd.jsonl'
for l in open(TSF):
    d = json.loads(l); R[(d['trace'], 'TSGD-' + d['mode'], d['cache_pct'])] = d
ALGS = ['LRU', 'LFUDA', 'GDS', 'GDSF', 'GDSTAR', 'KMGDSF', 'DMCM', 'TSGD-I', 'TSGD-IT', 'TSGD-ITC', 'BELADYSIZE']
NAMES = {'KMGDSF': 'k-Means-GDSF (2014)', 'DMCM': 'DMCM-core (2019)', 'TSGD-I': 'TS-GD: instantaneous only', 'TSGD-IT': 'TS-GD: + time series',
         'TSGD-ITC': 'TS-GD: + time series + clustering', 'BELADYSIZE': 'Belady-Size (offline bound)', 'GDSTAR': 'GD*', 'LFUDA': 'LFU-DA'}
SIZES = [0.001, 0.005, 0.01, 0.05, 0.1]
md = ['# Main results (cost C=1)\n']
for tr, title in [('wiki_s10', 'Wikipedia 2019 (10% sample), test days 14-20'), ('bluecoat_B', 'Blue Coat proxy B, test 3-6 May 2005')]:
    for met, mt in [('hit_ratio', 'Hit ratio %'), ('byte_hit_ratio', 'Byte hit ratio %')]:
        md.append(f'\n## {title} — {mt}\n\n| Policy | ' + ' | '.join(f'{100*s:g}%' for s in SIZES) + ' |\n|---|' + '---|' * len(SIZES))
        for a in ALGS:
            vals = [100 * R[(tr, a, s)][met] if (tr, a, s) in R else None for s in SIZES]
            row = []
            for s, v in zip(SIZES, vals):
                if v is None: row.append('-'); continue
                best = max(100 * R[(tr, b, s)][met] for b in ALGS if b != 'BELADYSIZE' and (tr, b, s) in R)
                row.append(f'**{v:.1f}**' if abs(v - best) < 1e-9 and a != 'BELADYSIZE' else f'{v:.1f}')
            md.append(f'| {NAMES.get(a, a)} | ' + ' | '.join(row) + ' |')
    md.append('\nGap to the offline bound closed by TS-GD (time series) relative to GDSF, hit ratio: ' + ', '.join(
        f"{100*s:g}%: {100*(R[(tr,'TSGD-IT',s)]['hit_ratio']-R[(tr,'GDSF',s)]['hit_ratio'])/(R[(tr,'BELADYSIZE',s)]['hit_ratio']-R[(tr,'GDSF',s)]['hit_ratio']):.0f}%" for s in SIZES))
open('results/main_results.md', 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
COL = {'LRU': '#2a78d6', 'LFUDA': '#eb6834', 'GDSF': '#eda100', 'KMGDSF': '#6250d6', 'DMCM': '#e34948', 'TSGD-IT': '#1baf7a', 'BELADYSIZE': '#0b0b0b'}
for tr, title in [('wiki_s10', 'Wikipedia 2019 (10% sample)'), ('bluecoat_B', 'Blue Coat proxy B')]:
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 4))
    for ax, met, lab in zip(axs, ['hit_ratio', 'byte_hit_ratio'], ['Hit ratio (%)', 'Byte hit ratio (%)']):
        for a in COL:
            ax.plot([100 * s for s in SIZES], [100 * R[(tr, a, s)][met] for s in SIZES], marker='o', ms=4, color=COL[a],
                    lw=2.6 if a == 'TSGD-IT' else 1.5, ls='--' if a == 'BELADYSIZE' else '-', label=NAMES.get(a, a).replace('TS-GD: + time series', 'TS-GD (proposed)'))
        ax.set_xscale('log'); ax.set_xlabel('Cache size (% of test-week unique bytes)'); ax.set_ylabel(lab)
        ax.grid(True, color='#e4e3df'); ax.spines[['top', 'right']].set_visible(False)
    axs[0].legend(frameon=False, fontsize=7.5); fig.suptitle(title + ': proposed model vs. baselines', x=0.01, ha='left', fontsize=10)
    fig.tight_layout(); fig.savefig(f'results/figures/fig7_main_{tr}.png', dpi=150); plt.close()
# ablation: improvement over GDSF (hit ratio points) per variant
fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.6), sharey=False)
for ax, tr, title in zip(axs, ['wiki_s10', 'bluecoat_B'], ['Wikipedia', 'Blue Coat B']):
    xs = range(len(SIZES)); wdt = 0.26
    for k, (a, c) in enumerate([('TSGD-I', '#9ec5ee'), ('TSGD-IT', '#1baf7a'), ('TSGD-ITC', '#6250d6')]):
        ax.bar([x + (k - 1) * wdt for x in xs], [100 * (R[(tr, a, s)]['hit_ratio'] - R[(tr, 'GDSF', s)]['hit_ratio']) for s in SIZES], wdt, color=c, label=NAMES[a])
    ax.axhline(0, color='#52514e', lw=0.8); ax.set_xticks(list(xs)); ax.set_xticklabels([f'{100*s:g}%' for s in SIZES])
    ax.set_title(title, loc='left', fontsize=10); ax.set_ylabel('Hit ratio gain over GDSF (points)'); ax.set_xlabel('Cache size')
    ax.grid(True, axis='y', color='#e4e3df'); ax.spines[['top', 'right']].set_visible(False)
axs[0].legend(frameon=False, fontsize=7.5); fig.tight_layout(); fig.savefig('results/figures/fig8_ablation_gain_over_gdsf.png', dpi=150); plt.close()
