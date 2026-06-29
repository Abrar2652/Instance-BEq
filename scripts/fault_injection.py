#!/usr/bin/env python3
"""Controlled fault-injection benchmark for check 2 (instance soundness).

Ground truth by construction:
  * each sound gold bridging instance  -> KNOWN SOUND
  * each instance with one condition field replaced by `by sorry` -> KNOWN HOLLOW
We then score two detectors on this labelled set:
  * Instance-BEq check 2  (axiom-closure: sorryAx/disallowed-axiom in the instance's closure)
  * baseline A type-check-only  (file compiles with 0 errors -> "faithful")
and report precision / recall / F1 with HOLLOW as the positive class.

This is the reviewer-proof precision anchor: check 2 is decidable, so it is EXACT (P=R=1),
while type-check-only is provably blind to every planted fault (sorry is a warning, not an error).

Run:  python scripts/fault_injection.py
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle

EXDIR = "Optlib/Autoformalization/Example"
# family -> (bridging instance, [condition fields = proof obligations to fault-inject])
FAMILIES = {
    "GD_example":            ("LeastSquares_GD.Gradient_Descent",
                              ["update", "hl", "step₁", "initial"]),
    "PGD_example":           ("proximal_gradient_method_Lasso.proximal_gradient_method",
                              ["initial", "update"]),
    "NesterovFirst_example": ("Nesterov_first_fix_stepsize_Lasso.Nesterov_first_fix_stepsize",
                              ["hl", "initial", "teq", "γeq", "update1", "update2"]),
    "NesterovSecond_example":("Nesterov_second_fix_stepsize_Lasso.Nesterov_second_fix_stepsize",
                              ["hl", "initial", "teq", "γeq", "update1", "update2", "update3"]),
}


def cert_check2(res, inst, allowed):
    """Instance-BEq check 2 verdict for `inst` from an oracle result."""
    axset = res.axioms.get(inst)
    if axset is None:
        return "unknown"
    if any(tok in a for a in axset for tok in SORRY_TOKENS) or any(a not in allowed for a in axset):
        return "hollow"
    return "sound"


def run(oracle, cfg, src, inst):
    res = oracle.check_snippet(src + f"\n#print axioms {inst}\n")
    return cert_check2(res, inst, cfg.allowed_axioms), res.ok  # (certifier, baselineA_typechecks)


def main():
    cfg = InstanceBEqConfig(mock=False)
    oracle = LeanOracle(cfg)
    root = cfg.lean_cwd
    items, t0 = [], time.time()

    for fam, (inst, fields) in FAMILIES.items():
        text = (root / EXDIR / f"{fam}.lean").read_text(encoding="utf-8")
        mod = f"import Optlib.Autoformalization.Example.{fam}"
        # KNOWN SOUND: original instance (import the built module, query axioms)
        c, ok = run(oracle, cfg, mod, inst)
        items.append({"family": fam, "case": "original", "field": None,
                      "truth": "sound", "certifier": c, "baselineA_typechecks": ok})
        # KNOWN HOLLOW: one condition field -> by sorry  (edit the full source, recompile)
        for fld in fields:
            patched, n = re.subn(rf"(\n\s*{re.escape(fld)}\s*:=)[^\n]*",
                                 rf"\1 by sorry", text, count=1)
            if n != 1:
                items.append({"family": fam, "case": f"sorry:{fld}", "field": fld,
                              "truth": "hollow", "certifier": "PLANT_FAILED",
                              "baselineA_typechecks": None})
                continue
            c, ok = run(oracle, cfg, patched, inst)
            items.append({"family": fam, "case": f"sorry:{fld}", "field": fld,
                          "truth": "hollow", "certifier": c, "baselineA_typechecks": ok})

    # ---- score: HOLLOW is the positive class --------------------------------
    def score(pred_is_hollow):
        tp = fn = fp = tn = 0
        for it in items:
            truth_pos = it["truth"] == "hollow"
            pred_pos = pred_is_hollow(it)
            tp += truth_pos and pred_pos
            fn += truth_pos and not pred_pos
            fp += (not truth_pos) and pred_pos
            tn += (not truth_pos) and (not pred_pos)
        P = tp / (tp + fp) if tp + fp else float("nan")
        R = tp / (tp + fn) if tp + fn else float("nan")
        F = 2 * P * R / (P + R) if P and R and (P + R) else 0.0
        return tp, fp, fn, tn, P, R, F

    cert = score(lambda it: it["certifier"] == "hollow")
    # baseline A calls a file "faithful" iff it type-checks (0 errors); it NEVER predicts hollow
    base = score(lambda it: it["baselineA_typechecks"] is False)

    n_h = sum(1 for it in items if it["truth"] == "hollow")
    n_s = sum(1 for it in items if it["truth"] == "sound")
    print(f"fault-injection benchmark: {len(items)} instances "
          f"({n_s} sound originals, {n_h} planted-hollow)  [{time.time()-t0:.0f}s]\n")
    print(f"{'method':<26}{'TP':>4}{'FP':>4}{'FN':>4}{'TN':>4}{'Prec':>8}{'Rec':>8}{'F1':>8}")
    for name, s in [("Instance-BEq check 2", cert), ("type-check-only (base A)", base)]:
        tp, fp, fn, tn, P, R, F = s
        print(f"{name:<26}{tp:>4}{fp:>4}{fn:>4}{tn:>4}{P:>8.3f}{R:>8.3f}{F:>8.3f}")

    # sanity: any certifier disagreement with ground truth?
    wrong = [it for it in items if it["certifier"] not in ("hollow", "sound")
             or (it["truth"] == "hollow") != (it["certifier"] == "hollow")]
    print(f"\ncertifier disagreements with ground truth: {len(wrong)}")
    for w in wrong:
        print("  ", w["family"], w["case"], "->", w["certifier"])

    out = Path(__file__).resolve().parents[1] / "eval_logs" / "fault_injection_result.json"
    out.write_text(json.dumps({"items": items,
                               "certifier": dict(zip("tp fp fn tn P R F1".split(), cert)),
                               "baselineA": dict(zip("tp fp fn tn P R F1".split(), base))},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")
    sys.exit(0 if len(wrong) == 0 else 1)


if __name__ == "__main__":
    main()
