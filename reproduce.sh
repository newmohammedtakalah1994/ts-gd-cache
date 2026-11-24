#!/bin/bash
# Reproduce the experiments of the thesis / paper, stage by stage. Every stage is resumable.
#   bash reproduce.sh build      compile the simulators (bin/)
#   bash reproduce.sh data       parse Blue Coat logs, build the binary traces (wiki_s10, bluecoat_B, wiki_full), unit-test the simulator
#   bash reproduce.sh eda        exploratory analysis of both traces + EDA figures
#   bash reproduce.sh baselines  classic policies + re-implemented 2014 / 2019 methods (10% sample and Blue Coat)
#   bash reproduce.sh tsgd       choose the prediction horizon on warm-up data, then TS-GD variants (10% sample and Blue Coat)
#   bash reproduce.sh full       classic policies + TS-GD on the full Wikipedia trace (several hours)
#   bash reproduce.sh extras     sensitivity (K, horizon) and robustness over random seeds
#   bash reproduce.sh report     tables (results/main_results.md, results/baselines_tables.md) and figures
#   bash reproduce.sh all        everything above, in order
# Modern baselines (LRB, GL-Cache, S3-FIFO, SIEVE, ...) need libCacheSim: see README.md, section "Modern baselines".
set -e
cd "$(dirname "$0")"
PY=${PY:-python3}; PAR=${PAR:-4}
mkdir -p data/processed results/figures
stage() {
  case "$1" in
    build) make all ;;
    data)
      for i in 1 2 3 4; do
        [ -f data/processed/bluecoat_00$i.npz ] || PYTHONHASHSEED=0 $PY scripts/parse_bluecoat.py data/bluecoat_raw/Demo_log_00$i.log data/processed/bluecoat_00$i.npz
      done
      [ -f data/processed/wiki_s10.bin.json ] || $PY scripts/prep_traces.py wiki 10
      [ -f data/processed/bluecoat_B.bin.json ] || $PY scripts/prep_traces.py bluecoat
      [ -f data/processed/wiki_full.bin.json ] || $PY scripts/prep_wiki_full.py
      make test ;;
    eda)
      $PY scripts/analyze_wiki.py data/wikipedia_text results 5000
      $PY scripts/analyze_bluecoat.py data/processed results
      $PY scripts/diag_timeseries_signal.py data/processed/wiki_s10.bin
      $PY scripts/diag_timeseries_signal.py data/processed/bluecoat_B.bin
      $PY scripts/make_figures.py ;;
    baselines)
      for tr in wiki_s10 bluecoat_B; do
        $PY scripts/features.py data/processed/$tr.bin
        $PY scripts/train_predict.py data/processed/$tr.bin kmeans
        $PY scripts/train_predict.py data/processed/$tr.bin knn
        $PY scripts/run_baselines.py data/processed/$tr.bin 100000 $PAR
      done ;;
    tsgd) $PY scripts/select_cap.py $PAR ;;
    full)
      $PY scripts/run_fullscale.py 2
      $PY scripts/run_fullscale_capsel.py 2 ;;
    extras)
      $PY scripts/run_sensitivity.py $PAR
      $PY scripts/run_seeds.py $PAR ;;
    report)
      $PY scripts/report_baselines.py
      $PY scripts/report_all.py ;;
    all) for s in build data eda baselines tsgd full extras report; do stage $s; done ;;
    *) echo "unknown stage: $1 (see the header of this script)"; exit 1 ;;
  esac
}
stage "${1:-all}"
