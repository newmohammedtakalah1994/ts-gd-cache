# Data

The raw traces are not included. Download them into this folder:

```
data/
├── wikipedia_text/        cache-t-00.gz … cache-t-20.gz
└── bluecoat_raw/          Demo_log_001.log … Demo_log_004.log
```

1. **Wikipedia CDN 2019** — Wikimedia Foundation, "Analytics datasets: caching (2019 release)":
   https://analytics.wikimedia.org/published/datasets/caching/2019/ — the 21 daily files of the **text** cluster
   (`cache-t-00.gz` … `cache-t-20.gz`, columns: relative_unix, hashed_host_path_query, response_size, time_firstbyte).
2. **Blue Coat proxy logs** — SecRepo, "Samples of security related data", `bluecoat_proxy_big`
   (https://www.secrepo.com): the four `Demo_log_00X.log` files. Proxy B = files 002 and 003; files 001 and 004
   (proxy A) are only used in the exploratory analysis.

`bash reproduce.sh data` then writes the processed traces to `data/processed/`:
`wiki_s10.bin` (10% sample, 19.9 M requests), `bluecoat_B.bin` (3.8 M requests) and `wiki_full.bin` (207.6 M requests),
each with a `.json` file describing it.
