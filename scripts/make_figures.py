"""Thesis figures for the exploratory data analysis (EDA) chapter."""
import numpy as np, json, os, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
R = 'results'; F = os.path.join(R, 'figures'); os.makedirs(F, exist_ok=True)
C = dict(wiki='#2a78d6', A='#eb6834', B='#1baf7a'); INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e4e3df'
plt.rcParams.update({'font.size': 10, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2,
                     'ytick.color': INK2, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
                     'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150, 'lines.linewidth': 1.6})
w = np.load(os.path.join(R, 'wiki_arrays.npz')); b = np.load(os.path.join(R, 'bc_arrays.npz'))

# 1. Hourly traffic, Wikipedia (21 days)
fig, ax = plt.subplots(figsize=(9, 3))
ax.plot(np.arange(len(w['hourly'])) / 24, w['hourly'] / 1e3, color=C['wiki'])
ax.set_xlabel('Day of trace'); ax.set_ylabel('Requests per hour (thousands)')
ax.set_title('Wikipedia CDN (text): hourly request volume over 21 days', loc='left', color=INK)
ax.set_xticks(range(0, 22, 7)); fig.tight_layout(); fig.savefig(f'{F}/fig1_wiki_hourly.png'); plt.close()

# 2. Popularity (rank-frequency)
fig, ax = plt.subplots(figsize=(6, 4))
for k, arr, lab in [('wiki', w['popularity'], 'Wikipedia 2019'), ('B', b['B_popularity'], 'Blue Coat proxy B'),
                    ('A', b['A_popularity'], 'Blue Coat proxy A')]:
    r = np.unique(np.logspace(0, np.log10(len(arr)), 400).astype(int)) - 1
    ax.loglog(r + 1, arr[r], color=C[k], label=lab)
ax.set_xlabel('Object rank'); ax.set_ylabel('Number of requests')
ax.set_title('Object popularity (Zipf-like)', loc='left', color=INK); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(f'{F}/fig2_popularity_zipf.png'); plt.close()

# 3. Daily periodicity of popular objects: distribution of ACF at lag 24h
fig, ax = plt.subplots(figsize=(6, 4)); bins = np.linspace(-0.4, 1, 36)
for k, arr, lab in [('wiki', w['acf24'], 'Wikipedia (top 5000)'), ('B', b['B_acf24'], 'Blue Coat B (top 2000)'),
                    ('A', b['A_acf24'], 'Blue Coat A (top 2000)')]:
    arr = arr[~np.isnan(arr)]
    ax.hist(arr, bins=bins, histtype='step', linewidth=2, color=C[k], density=True, label=lab)
ax.axvline(0.3, color=INK2, linestyle='--', linewidth=1); ax.text(0.31, ax.get_ylim()[1] * 0.92, 'periodic ≥ 0.3', color=INK2, fontsize=8)
ax.set_xlabel('Autocorrelation at 24-hour lag (per object)'); ax.set_ylabel('Density')
ax.set_title('How strongly do popular objects repeat daily?', loc='left', color=INK); ax.legend(frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(f'{F}/fig3_daily_periodicity_acf24.png'); plt.close()

# 4. Heatmap: 60 popular Wikipedia objects, first 7 days, rows normalised, sorted by ACF24
M = w['M'][:, :24 * 7].astype(float); a = w['acf24']
idx = np.argsort(-a)[np.linspace(0, len(a) - 1, 60).astype(int)]
X = M[idx]; X = (X - X.mean(1, keepdims=True)) / (X.std(1, keepdims=True) + 1e-9)
fig, ax = plt.subplots(figsize=(9, 4.2)); ax.grid(False)
im = ax.imshow(X, aspect='auto', cmap='Blues', vmin=-1, vmax=2.5, interpolation='nearest')
ax.set_xticks(range(0, 24 * 7 + 1, 24)); ax.set_xticklabels([f'day {d}' for d in range(8)])
ax.set_yticks([0, 59]); ax.set_yticklabels(['most periodic', 'least periodic'])
ax.set_title('Hourly requests of 60 popular objects (one row each, 7 days)', loc='left', color=INK)
fig.colorbar(im, ax=ax, label='normalised requests (z)', shrink=0.8)
fig.tight_layout(); fig.savefig(f'{F}/fig4_periodic_objects_heatmap.png'); plt.close()

# 5. Blue Coat hourly traffic (cacheable requests), proxy A and B
fig, axs = plt.subplots(2, 1, figsize=(9, 4.5), sharex=False)
for ax, g in zip(axs, ['A', 'B']):
    h = b[f'{g}_hourly']; t0 = int(b[f'{g}_t0'])
    s0 = int(np.argmax(h > 0.01 * h.max())) // 24 * 24     # skip the near-empty early weeks
    t = (t0 + 3600 * np.arange(s0, len(h))).astype('datetime64[s]')
    ax.plot(t, h[s0:] / 1e3, color=C[g]); ax.set_ylabel('k req / hour')
    ax.set_title(f'Blue Coat proxy {g}: cacheable requests per hour (active period only)', loc='left', color=INK, fontsize=9)
    import matplotlib.dates as mdates; ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
axs[-1].set_xlabel('Date (2005, UTC)'); fig.tight_layout(); fig.savefig(f'{F}/fig5_bluecoat_hourly.png'); plt.close()
print(sorted(os.listdir(F)))
