# Full Wikipedia trace (207.6 M requests; test days 14-20, 62.4 M requests): TS-GD against libCacheSim

## Hit ratio %

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| TS-GD (IT) | **23.4** | **40.4** | **49.7** | **72.2** | **80.1** |
| GDSF (our simulator) | 19.9 | 37.2 | 46.7 | 69.9 | 78.4 |
| LFU-DA (our simulator) | 18.0 | 35.0 | 44.6 | 67.9 | 76.6 |
| GDSF (libCacheSim) | 21.8 | 39.2 | 48.2 | 70.7 | 79.1 |
| S3-FIFO | 19.6 | 35.9 | 45.2 | 68.8 | 77.7 |
| SIEVE | 19.0 | 34.8 | 44.2 | 69.0 | 78.0 |
| GL-Cache | 11.3 | 25.0 | 28.9 | 57.1 | 71.1 |
| LRB | 16.9 | 35.8 | 45.5 | 69.9 | 78.6 |
| Belady-Size (offline bound) | 34.5 | 52.0 | 60.5 | 79.3 | 85.7 |

## Byte hit ratio %

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| TS-GD (IT) | 25.0 | 44.6 | 54.3 | 75.6 | 82.3 |
| GDSF (our simulator) | 20.2 | 40.3 | 50.9 | 74.2 | 81.7 |
| LFU-DA (our simulator) | 23.7 | 44.8 | 55.1 | 76.5 | 83.2 |
| GDSF (libCacheSim) | 25.7 | 45.0 | 54.2 | 75.4 | 82.6 |
| S3-FIFO | **26.1** | 45.9 | 55.9 | 77.3 | 84.0 |
| SIEVE | 25.8 | 45.3 | 55.4 | 77.4 | 84.2 |
| GL-Cache | 10.9 | 24.6 | 26.8 | 59.1 | 75.0 |
| LRB | 23.7 | **46.7** | **57.0** | **78.4** | **84.9** |
| Belady-Size (offline bound) | 35.6 | 54.7 | 63.6 | 81.9 | 87.7 |

## Wall-clock time of the libCacheSim runs (hours; Windows laptop, WSL2, one run at a time)

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| GDSF (libCacheSim) | 0.30 | 0.30 | 0.32 | 0.34 | 0.35 |
| S3-FIFO | 0.30 | 0.30 | 0.30 | 0.30 | 0.29 |
| SIEVE | 0.31 | 0.29 | 0.29 | 0.29 | 0.29 |
| GL-Cache | 0.30 | 0.30 | 0.30 | 0.30 | 0.30 |
| LRB | 5.31 | 5.16 | 4.74 | 3.59 | 3.05 |

Wall time includes reading the 4.7 GB trace from the Windows file system, which dominates the time of the fast policies.
Hit ratios do not depend on the machine; times measured on different machines must not be compared directly.
