#!/usr/bin/env bash
# Regenerate every Instance-BEq paper figure from real result files, in one command.
# Figures land in paper/figures/*.pdf (vector). Run scripts/soundness_all_methods.py first if the
# unified soundness file is stale.
set -e
cd "$(dirname "$0")"
python3 ../soundness_all_methods.py
python3 ../score_methods_vs_gold.py >/dev/null   # 5 methods × 4 checks vs human gold (+ Kendall τ)
python3 ../bootstrap_ci.py >/dev/null            # 95% bootstrap CIs (used by fig_methods_f1/tables)
for f in fig_overview fig_methods_f1 fig_ablations fig_prf_soundness fig_gold_hollow \
         fig_check1_defeq fig_catch_matrix fig_pr_tradeoff fig_tau_human fig_calibration; do
  echo "== $f =="
  python3 "$f.py"
done
echo "all figures regenerated into paper/figures/"
