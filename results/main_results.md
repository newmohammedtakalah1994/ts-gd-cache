# Main results (cost C=1)


## Wikipedia 2019 (10% sample), test days 14-20 — Hit ratio %

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| LRU | 11.4 | 25.8 | 34.9 | 60.5 | 70.8 |
| LFU-DA | 15.6 | 32.8 | 42.8 | 66.8 | 75.8 |
| GDS | 12.3 | 27.0 | 36.0 | 62.1 | 72.9 |
| GDSF | 17.8 | 35.2 | 44.9 | 68.8 | 77.6 |
| GD* | 14.9 | 31.4 | 41.0 | 66.1 | 75.7 |
| k-Means-GDSF (2014) | 14.5 | 32.5 | 41.5 | 68.6 | 77.5 |
| DMCM-core (2019) | 14.0 | 30.8 | 37.2 | 56.4 | 69.0 |
| TS-GD: instantaneous only | 21.3 | 38.1 | 47.5 | 70.9 | 79.4 |
| TS-GD: + time series | **21.4** | **38.4** | **48.0** | 71.1 | 79.3 |
| TS-GD: + time series + clustering | 21.4 | 38.4 | 48.0 | **71.2** | **79.4** |
| Belady-Size (offline bound) | 32.4 | 50.3 | 59.0 | 78.5 | 85.2 |

## Wikipedia 2019 (10% sample), test days 14-20 — Byte hit ratio %

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| LRU | 14.2 | 31.4 | 42.2 | 69.1 | 77.9 |
| LFU-DA | 19.8 | 41.4 | **52.4** | **75.1** | **82.0** |
| GDS | 11.8 | 26.6 | 36.1 | 64.3 | 75.2 |
| GDSF | 17.2 | 36.6 | 47.6 | 72.5 | 80.4 |
| GD* | 16.0 | 35.0 | 46.1 | 72.1 | 80.5 |
| k-Means-GDSF (2014) | 19.0 | **42.3** | 52.1 | 72.8 | 80.5 |
| DMCM-core (2019) | 15.7 | 37.5 | 47.3 | 62.3 | 72.8 |
| TS-GD: instantaneous only | **21.5** | 40.8 | 50.6 | 73.6 | 81.1 |
| TS-GD: + time series | 21.5 | 41.2 | 51.3 | 74.0 | 81.1 |
| TS-GD: + time series + clustering | 21.5 | 41.1 | 51.2 | 74.1 | 81.2 |
| Belady-Size (offline bound) | 32.5 | 51.8 | 61.2 | 80.7 | 86.8 |

Gap to the offline bound closed by TS-GD (time series) relative to GDSF, hit ratio: 0.1%: 25%, 0.5%: 21%, 1%: 22%, 5%: 24%, 10%: 23%

## Blue Coat proxy B, test 3-6 May 2005 — Hit ratio %

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| LRU | 25.0 | 42.0 | 49.1 | 63.5 | 68.2 |
| LFU-DA | 26.9 | 41.4 | 47.8 | 61.9 | 66.2 |
| GDS | 42.1 | 60.0 | 66.2 | 76.2 | 77.8 |
| GDSF | 44.5 | **61.8** | **67.7** | **76.7** | **78.0** |
| GD* | 41.5 | 58.8 | 64.7 | 75.5 | 77.6 |
| k-Means-GDSF (2014) | 30.2 | 49.1 | 55.4 | 66.1 | 70.7 |
| DMCM-core (2019) | 35.8 | 48.3 | 51.7 | 55.7 | 63.5 |
| TS-GD: instantaneous only | 44.7 | 61.3 | 66.9 | 75.4 | 77.2 |
| TS-GD: + time series | 44.6 | 61.4 | 66.9 | 75.3 | 77.3 |
| TS-GD: + time series + clustering | **44.7** | 61.4 | 66.9 | 75.2 | 77.2 |
| Belady-Size (offline bound) | 52.8 | 68.6 | 73.4 | 79.1 | 79.1 |

## Blue Coat proxy B, test 3-6 May 2005 — Byte hit ratio %

| Policy | 0.1% | 0.5% | 1% | 5% | 10% |
|---|---|---|---|---|---|
| LRU | 36.7 | **63.9** | **68.2** | **76.8** | **81.2** |
| LFU-DA | 36.8 | 63.8 | 67.4 | 76.6 | 81.0 |
| GDS | 19.4 | 32.0 | 37.2 | 55.0 | 65.0 |
| GDSF | 20.5 | 34.9 | 41.3 | 59.0 | 71.2 |
| GD* | 28.4 | 51.3 | 59.1 | 75.7 | 80.2 |
| k-Means-GDSF (2014) | **37.3** | 63.3 | 66.6 | 73.2 | 77.8 |
| DMCM-core (2019) | 29.5 | 55.1 | 61.7 | 69.7 | 75.0 |
| TS-GD: instantaneous only | 30.2 | 55.2 | 63.0 | 75.3 | 79.3 |
| TS-GD: + time series | 30.0 | 54.9 | 62.8 | 74.9 | 79.5 |
| TS-GD: + time series + clustering | 30.3 | 55.2 | 62.7 | 75.5 | 79.5 |
| Belady-Size (offline bound) | 31.4 | 53.9 | 61.0 | 80.2 | 83.6 |

Gap to the offline bound closed by TS-GD (time series) relative to GDSF, hit ratio: 0.1%: 1%, 0.5%: -6%, 1%: -14%, 5%: -59%, 10%: -73%
