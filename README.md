# TS-GD: Time-Series-aware Greedy-Dual cache replacement

Code and experiments of the master's thesis **"Mining Time Series in Caching Proxy Data Stream"**
(Muhammad Takalah, supervised by Dr. Bassem Kossayba, Faculty of Informatics Engineering, Damascus University, 2026).

TS-GD is a cache replacement policy for web proxy / CDN caches. At every eviction it samples K = 64 cached objects,
predicts for each one the logarithm of the time until its next request with an online ridge regression
(instantaneous features + features of the object's daily request profile), and evicts the object with the largest
`predicted log time + log size`, a learned approximation of the offline Belady-Size algorithm. The model is retrained
every 6 hours on the last 3 days of samples whose label is already known, so it never looks into the future.

## Main results (hit ratio %, full Wikipedia CDN 2019 trace, 207.6 M requests, test week = last 7 days)

| cache size (% of test-week unique bytes) | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| TS-GD (IT, proposed) | **23.4** | **40.4** | **49.7** | **72.2** | **80.1** |
| GDSF | 19.9 | 37.2 | 46.7 | 69.9 | 78.4 |
| LFU-DA | 18.0 | 35.0 | 44.6 | 67.9 | 76.6 |
| LRU | 13.7 | 28.2 | 37.2 | 61.9 | 71.8 |
| Belady-Size (offline bound) | 34.5 | 52.0 | 60.5 | 79.3 | 85.7 |

TS-GD closes 21–25% of the gap between GDSF and Belady-Size at every cache size. It also has the highest hit ratio of
all compared policies, including LRB, GL-Cache, S3-FIFO, SIEVE and libCacheSim's own GDSF, at every size, both on the
full trace and on a 10% spatial sample; LRB (from a 0.5% cache) and S3-FIFO (at 0.1%) have a higher byte hit ratio, but
a full-trace run of LRB takes 3.1–5.3 hours, against 17–21 minutes for the other policies. Full tables: `results/main_results.md`, `results/libcachesim_full.md`
and the JSON-lines files in `results/` (the reference outputs of all runs).

## Repository layout

| path | content |
|---|---|
| `src/cachesim.cpp` | simulator of the baselines: LRU, LFU-DA, GDS, GDSF, GD*, k-Means-GDSF (2014), DMCM-core (2019), Belady, Belady-Size |
| `src/tsgdsim.cpp` | simulator of the proposed model and its variants |
| `scripts/` | trace preparation, experiment runners (all resumable), analysis and report scripts |
| `reproduce.sh` | runs everything stage by stage |
| `results/` | reference results (`*.jsonl`, tables, figures) produced by these scripts |
| `data/` | put the raw traces here (see `data/README.md`); not part of the repository |

## Requirements

- A C++17 compiler (`clang++` on macOS, `g++` on Linux) and `make`
- Python 3.10+ with `pip install -r requirements.txt` (numpy, pandas, matplotlib, scikit-learn)
- Memory: 16 GB is enough for everything (libCacheSim on the full Wikipedia trace peaks at about 7 GB)
- Disk: about 15 GB for the processed traces

## Quick start

```bash
make                       # builds bin/cachesim and bin/tsgdsim
bash reproduce.sh data     # after downloading the traces into data/ (see data/README.md); ends with `make test`
bash reproduce.sh tsgd     # main TS-GD experiments on the 10% sample and Blue Coat
```

`bash reproduce.sh all` runs every stage: `build`, `data`, `eda`, `baselines`, `tsgd`, `full`, `extras`, `report`.
Set `PAR` (parallel runs, default 4) and `PY` (Python interpreter) as environment variables if needed.

## Running the simulators directly

Traces are binary files of records `(uint32 time_s, uint32 object_id, uint32 size_bytes, float32 cost)`, with a
`.json` file next to each one that gives `test_start` (start of the measured period) and `working_set_bytes`.

```bash
# baseline: <trace> <policy> <cache_bytes> <test_start> <cost: one|latency> [beta for GD*]
bin/cachesim data/processed/bluecoat_B.bin GDSF 100000000 432000 one

# TS-GD: <trace> <cache_bytes> <test_start> <MODE> [K=64] [clusters=8] [theta=0.9]
#   MODE letters: I instantaneous, T time series, C clustering, S shrinkage, R regimes, G admission, A first-time admission
TSGD_CAP_HOURS=24 bin/tsgdsim data/processed/bluecoat_B.bin 100000000 432000 IT
```

Environment variables of `tsgdsim`: `TSGD_CAP_HOURS` (prediction horizon, default 24), `TSGD_SEED` (random seed,
default 42), `TSGD_DUMP` (path: write one byte per request, 1 = hit). Both simulators print one JSON line with the hit
ratio, byte hit ratio and run time; `tsgdsim` also prints the learned weights.

## Experimental protocol

- **Wikipedia CDN 2019** (`cache-t`, 21 days): days 0–13 warm-up and training, days 14–20 test. Development and modern
  baselines on a 10% spatial sample (objects selected by hash, each object's full history kept); confirmation on the
  full trace.
- **Blue Coat proxy B** (SecRepo, files 002 + 003, cacheable GET requests): warm-up 28 Apr – 2 May 2005, test 3–6 May.
- **Prediction horizon** chosen on warm-up data only (`scripts/select_cap.py`): days 0–13 of the sample, measured on
  days 10–13, from {24, 48, 72, 120} h → 24 h up to a 1% cache, 120 h at 5% and 10% (`results/cap_choice.json`).
- Fetch cost C = 1 (the recorded latency includes cache hits and is not a fetch cost).

## Modern baselines (libCacheSim)

LRB, GL-Cache, S3-FIFO, SIEVE, S4-FIFO, W-TinyLFU, ARC and libCacheSim's own GDSF / LRU / Belady-Size are run with
[libCacheSim](https://github.com/1a1a11a/libCacheSim) (version 0.3.5) under the same protocol:

```bash
git clone https://github.com/1a1a11a/libCacheSim tools/libCacheSim
# build it with -DENABLE_LRB=ON -DENABLE_GLCACHE=ON -DENABLE_S4FIFO=ON (see its README; on macOS install argp-standalone)
python3 scripts/to_oracle_general.py data/processed/wiki_s10.bin
python3 scripts/run_libcachesim.py tools/libCacheSim/_build/bin/cachesim 4 data/processed/bluecoat_B.bin data/processed/wiki_s10.bin
```

On the full Wikipedia trace we ran GDSF, S3-FIFO, SIEVE, GL-Cache and LRB, one run at a time:

```bash
python3 scripts/to_oracle_general.py data/processed/wiki_full.bin
LCS_ALGS=gdsf,s3fifo,sieve,GLCache,lrb python3 scripts/run_libcachesim.py tools/libCacheSim/_build/bin/cachesim 1 data/processed/wiki_full.bin
```

These runs were made on an x86-64 laptop with 32 GB of memory (Ubuntu under WSL2); the peak memory of a run was
4.8–7.2 GB. The full-trace results are in `results/sim_libcachesim.jsonl` (`"trace": "wiki_full"`).

## Citation

If you use this code, please cite the thesis (and the paper, once published):

```
M. Takalah, "Mining Time Series in Caching Proxy Data Stream", Master's thesis, Faculty of Informatics Engineering,
Damascus University, 2026.
```

## License

MIT (see `LICENSE`). The traces belong to their publishers (Wikimedia Foundation, SecRepo) and are not redistributed here.
