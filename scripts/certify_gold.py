#!/usr/bin/env python3
"""Real-mode check-2 (instance soundness) over the gold SITA examples + planted hollow faults.

This is a CONTROLLED validation of the headline check on real Lean (no LLM, no GPU):
  * every gold bridging instance must certify SOUND (sorry-free axiom closure), and
  * a planted `sorry` in a condition field must be CAUGHT (sorryAx enters the closure),
  * while type-check-only stays blind (the file still compiles; sorry is only a warning).

It drives the *real* `LeanOracle` + `#print axioms`, so the numbers are reproducible through the
package, not ad-hoc probes. Writes a JSON + prints a table.

Run:  python scripts/certify_gold.py
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle

EXAMPLES = "Optlib/Autoformalization/Example"
# family -> (bridging instance, planted-field-or-None, EXPECTED gold verdict)
# Expected verdicts are the GROUND TRUTH for this controlled test, established by inspecting the
# gold sources: GD/PGD/Nesterov are fully proven; ADMM/BCD carry `sorry` in condition fields
# (consistent with SITA Table 2: ADMM PS=20%, BCD=50.55%). The certifier must reproduce these.
GOLD = {
    "GD_example":            ("LeastSquares_GD.Gradient_Descent",            "hl",  "faithful"),
    "PGD_example":           ("proximal_gradient_method_Lasso.proximal_gradient_method", None, "faithful"),
    "BCD_example":           ("BCD_JointSparse.BCD",                         None,  "unfaithful"),
    "ADMM_example":          ("Lasso_ADMM.toADMM",                           None,  "unfaithful"),
    "NesterovFirst_example": ("Nesterov_first_fix_stepsize_Lasso.Nesterov_first_fix_stepsize", None, "faithful"),
    "NesterovSecond_example":("Nesterov_second_fix_stepsize_Lasso.Nesterov_second_fix_stepsize", None, "faithful"),
}


def soundness_verdict(axset, allowed):
    """sound iff every axiom is in the allowed set and none is a sorry token."""
    if axset is None:
        return "unknown", []
    bad = [a for a in axset
           if any(tok in a for tok in SORRY_TOKENS) or a not in allowed]
    return ("unfaithful" if bad else "faithful"), bad


def certify(oracle, cfg, module_suffix, inst, source_override=None):
    """Compile `import <module>; #print axioms <inst>` (or an overridden source) and judge."""
    mod = f"Optlib.Autoformalization.Example.{module_suffix}"
    if source_override is None:
        src = f"import {mod}\n#print axioms {inst}\n"
    else:
        src = source_override
    res = oracle.check_snippet(src)
    axset = res.axioms.get(inst)
    verdict, bad = soundness_verdict(axset, cfg.allowed_axioms)
    return {
        "instance": inst, "verdict": verdict, "axioms": axset, "bad": bad,
        "compiles": res.ok, "uses_sorry_warning": res.uses_sorry,
        "errors": [e["message"][:120] for e in res.errors[:3]],
    }


def main():
    cfg = InstanceBEqConfig(mock=False)
    oracle = LeanOracle(cfg)
    lean_root = cfg.lean_cwd
    rows, t0 = [], time.time()

    print(f"{'family':<22}{'instance':<52}{'gold (exp)':<22}{'planted-hollow':<16}")
    print("-" * 112)
    for mod_suffix, (inst, planted_field, expected) in GOLD.items():
        # --- gold instance: verdict must match the established ground truth ---
        gold = certify(oracle, cfg, mod_suffix, inst)
        gold["expected"] = expected

        # --- planted hollow variant: corrupt one condition field with sorry, must be CAUGHT ---
        hollow = None
        if planted_field:
            ex = (lean_root / EXAMPLES / f"{mod_suffix}.lean").read_text(encoding="utf-8")
            # replace the first `<field> := <proof>` with `<field> := by sorry`
            patched, n = re.subn(rf"(\n\s*{planted_field}\s*:=)[^\n]+",
                                 rf"\1 by sorry  -- PLANTED HOLLOW", ex, count=1)
            if n == 1:
                patched += f"\n#print axioms {inst}\n"
                hollow = certify(oracle, cfg, mod_suffix, inst, source_override=patched)
            else:
                hollow = {"verdict": "PLANT_FAILED", "axioms": None}

        rows.append({"family": mod_suffix, "gold": gold, "hollow": hollow})
        g = f"{gold['verdict']}"
        h = (hollow['verdict'] if hollow else "—")
        flag_g = "✓" if gold['verdict'] == expected else "✗"
        flag_h = "✓" if (hollow and hollow['verdict'] == "unfaithful") else ("—" if not hollow else "✗")
        print(f"{mod_suffix:<22}{inst[:50]:<52}{flag_g+' '+g+' ('+expected+')':<22}{flag_h+' '+h:<16}")

    # summary — the controlled test passes iff every gold verdict matches ground truth and every
    # planted fault is caught (no 'unknown', no misclassification).
    matched  = sum(1 for r in rows if r["gold"]["verdict"] == r["gold"]["expected"])
    sound_ok = sum(1 for r in rows if r["gold"]["verdict"] == "faithful")
    hollow_detected = sum(1 for r in rows if r["gold"]["verdict"] == "unfaithful")
    caught   = sum(1 for r in rows if r["hollow"] and r["hollow"]["verdict"] == "unfaithful")
    planted  = sum(1 for r in rows if r["hollow"])
    print("-" * 112)
    print(f"gold verdicts matching ground truth : {matched}/{len(rows)}  "
          f"(sound={sound_ok}, hollow-detected={hollow_detected})")
    print(f"planted hollow faults CAUGHT        : {caught}/{planted}")
    print(f"wall: {time.time()-t0:.1f}s")

    out = Path(__file__).resolve().parents[1] / "eval_logs" / "certify_gold_result.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    # PASS iff certifier reproduces ground truth on every family and catches every planted fault.
    sys.exit(0 if (matched == len(rows) and caught == planted) else 1)


if __name__ == "__main__":
    main()
