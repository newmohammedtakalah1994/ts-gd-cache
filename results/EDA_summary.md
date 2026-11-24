# Exploratory Data Analysis (EDA): summary of results — 23 Nov 2026

## Data
| | Wikipedia CDN text 2019 | Blue Coat proxy A (001+004) | Blue Coat proxy B (002+003) |
|---|---|---|---|
| Analysed requests | 207.6 M (all) | 1.40 M (cacheable GET only) | 3.80 M (cacheable GET only) |
| Unique objects | 18.4 M | 343 K | 844 K |
| Continuous period | 21 full days (504 h) | 164 h (~7 days) | 202 h (~8.4 days) |
| One-hit wonders | 55.7% | 64.0% | 63.8% |
| Max hit ratio (infinite cache) | 91.1% | 75.4% | 77.8% |
| Request share of top 1% of objects | 55.5% | 37.5% | 41.6% |
| Zipf alpha | 0.74 | 0.94 | 0.92 |
| Total-traffic ACF at 24 h | 0.86 | 0.53 | 0.62 |
| Popular objects with daily periodicity (ACF24 >= 0.3) | 75.7% of top 5000 | 30.8% of top 2000 | 65.6% of top 2000 |
| Median ACF24 for popular objects | 0.47 | 0.21 | 0.40 |

Additional Wikipedia findings: total-traffic ACF at 168 h (weekly) = 0.57; 41% of popular objects show a weekly pattern;
mean overlap (Jaccard) of the daily top-1000 objects between consecutive days = 0.53; 59% of objects appear on one day only.

Blue Coat notes: traffic is concentrated in 28 Apr – 6 May 2005 and grows sharply from day to day (non-stationary);
proxy A has an almost empty gap on 5–6 May; ~33–41% of requests are TCP_NC_MISS (non-cacheable) and were excluded;
no duplication between files 002 and 003; the two proxies share some clients (same organisation, two appliances).

## Figures (results/figures)
fig1 hourly Wikipedia traffic · fig2 popularity distribution · fig3 per-object ACF24 distribution · fig4 heatmap of popular objects · fig5 Blue Coat traffic

## Reproduce
python3 code/analyze_wiki.py data/wikipedia_text results 5000 pass1 ; ... pass2:0:11 ; ... all
PYTHONHASHSEED=0 python3 code/parse_bluecoat.py <log> data/processed/bluecoat_00X.npz ; python3 code/analyze_bluecoat.py data/processed results ; python3 code/make_figures.py
