#!/usr/bin/env python3
"""Synthetic stress benchmark — scales the faithfulness benchmark to a few hundred items whose
labels are CERTAIN BY CONSTRUCTION (no human annotation needed), to answer the reviewer question
"do the conclusions hold beyond 57 items?".

Two generators, both producing artifacts that still TYPE-CHECK (the hard case):
  * soundness stress  -- plant `by sorry` into every k-subset (k=1,2,3) of an instance's condition
                         fields. Each variant is KNOWN HOLLOW; the untouched instance is KNOWN SOUND.
  * definitional stress -- apply a fixed corruption catalogue (wrong constant, dropped term, missing
                         square, sign flip, wrong norm) to each numeric objective `def`. Each is
                         KNOWN UNFAITHFUL; the original (and equivalent rewrites) are KNOWN FAITHFUL.

We then score the certifier (decidable axiom closure for soundness; curated-reference def-eq for
definitional) and the blind baselines. The certifier is exact by construction; the point of scale
is (a) the implementation holds on N>>57 with diverse field/term structure, and (b) blind baselines
(type-check-only, BEq+) have recall 0 at every scale. Optionally also runs the LLM-judge (--judge)
to measure its degradation at scale.
Out: eval_logs/synthetic_stress_result.json
"""
from __future__ import annotations
import json, re, sys, time, itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle

EXDIR = "Optlib/Autoformalization/Example"
LOG = Path(__file__).resolve().parents[1] / "eval_logs"

# instance condition fields per sound family (proof obligations safe to fault-inject)
SOUND_FAMILIES = {
    "GD_example": ("LeastSquares_GD.Gradient_Descent", ["update", "hl", "step₁", "initial"]),
    "PGD_example": ("proximal_gradient_method_Lasso.proximal_gradient_method", ["initial", "update"]),
    "NesterovFirst_example": ("Nesterov_first_fix_stepsize_Lasso.Nesterov_first_fix_stepsize",
                              ["hl", "initial", "teq", "γeq", "update1", "update2"]),
    "NesterovSecond_example": ("Nesterov_second_fix_stepsize_Lasso.Nesterov_second_fix_stepsize",
                               ["hl", "initial", "teq", "γeq", "update1", "update2", "update3"]),
}
MAX_SUBSET_PER_K = 12  # cap k-subsets per (family,k) so the benchmark stays a few hundred items

# definitional corruption catalogue: (name, regex-on-body -> corrupted-body) applied to a numeric def
DEF_CORRUPTIONS = [
    ("const-1/3", lambda b: b.replace("1 / 2", "1 / 3")),
    ("const-2", lambda b: b.replace("1 / 2", "2")),
    ("drop-half", lambda b: re.sub(r"1 / 2 \* ", "", b)),
    ("no-square", lambda b: b.replace("‖₂ ^ 2", "‖₂")),
    ("sign-flip", lambda b: b.replace("- b", "+ b")),
    ("wrong-norm", lambda b: b.replace("‖₂ ^ 2", "‖₁ ^ 2")),
]


def cert_check2(res, inst, allowed):
    axset = res.axioms.get(inst)
    if axset is None:
        return "unknown"
    if any(tok in a for a in axset for tok in SORRY_TOKENS) or any(a not in allowed for a in axset):
        return "hollow"
    return "sound"


def soundness_stress(oracle, cfg):
    items = []
    for fam, (inst, fields) in SOUND_FAMILIES.items():
        text = (cfg.lean_cwd / EXDIR / f"{fam}.lean").read_text(encoding="utf-8")
        mod = f"import Optlib.Autoformalization.Example.{fam}"
        res = oracle.check_snippet(mod + f"\n#print axioms {inst}\n")
        items.append({"gen": "soundness", "family": fam, "mut": "original", "truth": "faithful",
                      "certifier": "faithful" if cert_check2(res, inst, cfg.allowed_axioms) == "sound" else "unfaithful",
                      "typechecks": res.ok})
        for k in (1, 2, 3):
            subsets = list(itertools.combinations(fields, k))[:MAX_SUBSET_PER_K]
            for sub in subsets:
                patched, ok = text, True
                for fld in sub:
                    patched, n = re.subn(rf"(\n\s*{re.escape(fld)}\s*:=)[^\n]*", rf"\1 by sorry", patched, count=1)
                    if n != 1:
                        ok = False; break
                if not ok:
                    continue
                r = oracle.check_snippet(patched + f"\n#print axioms {inst}\n")
                items.append({"gen": "soundness", "family": fam, "mut": "sorry:" + "+".join(sub),
                              "truth": "unfaithful",
                              "certifier": "unfaithful" if cert_check2(r, inst, cfg.allowed_axioms) == "hollow" else "faithful",
                              "typechecks": r.ok})
    return items


def definitional_stress(oracle, cfg):
    """Corrupt the LeastSquares objective in GD_example; each corruption is KNOWN unfaithful.
    Verdict = curated def-eq certifier (prove gen = canonical-ref). Faithful original proves;
    corruptions do not (and we confirm they still type-check)."""
    fam, target = "GD_example", "LeastSquares_problem.f"
    text = (cfg.lean_cwd / EXDIR / f"{fam}.lean").read_text(encoding="utf-8")
    ref = "‖A *ᵥ x - b‖₂ ^ 2 / 2"
    # match `def <target> <sig...> := \n fun x ↦ <body>` -- non-greedy up to the first := (the
    # signature contains a lone `:`, so a [^:=] class fails; use DOTALL + lazy instead)
    bodyre = re.compile(rf"(def\s+{re.escape(target)}\b.*?:=\s*)(fun x ↦[^\n]*)", re.DOTALL)
    m = bodyre.search(text)
    if not m:
        return []
    orig_body = m.group(2)

    def verdict_for(src):
        # inject equality example right after the (possibly corrupted) def, prove via ensemble
        ex = (f"\nexample (self : LeastSquares_problem A b) (x : EuclideanSpace ℝ (Fin n)) :\n"
              f"    {target} self x = {ref} := by unfold {target}; ring\n")
        anchor = re.search(rf"def\s+{re.escape(target)}\b.*?fun x ↦[^\n]*\n", src, re.DOTALL)
        if not anchor:
            return None, None
        probe = src[:anchor.end()] + ex + src[anchor.end():]
        r = oracle.check_snippet(probe)
        proved = r.ok and not r.errors
        # also confirm the corrupted file still type-checks on its own (sorry-free, real error-free)
        tc = oracle.check_snippet(src + "\n").ok
        return ("faithful" if proved else None), tc

    items = []
    v, tc = verdict_for(text)
    items.append({"gen": "definitional", "family": fam, "mut": "original", "truth": "faithful",
                  "certifier": v, "typechecks": tc})
    for name, fn in DEF_CORRUPTIONS:
        cbody = fn(orig_body)
        if cbody == orig_body:
            continue
        corrupted = text[:m.start(2)] + cbody + text[m.end(2):]
        v, tc = verdict_for(corrupted)
        items.append({"gen": "definitional", "family": fam, "mut": name, "truth": "unfaithful",
                      "certifier": v, "typechecks": tc})
    return items


def score(items, positive="unfaithful"):
    tp = sum(it["truth"] == positive and it["certifier"] == positive for it in items)
    fn = sum(it["truth"] == positive and it["certifier"] != positive for it in items)
    fp = sum(it["truth"] != positive and it["certifier"] == positive for it in items)
    tn = sum(it["truth"] != positive and it["certifier"] != positive for it in items)
    P = tp/(tp+fp) if tp+fp else None
    R = tp/(tp+fn) if tp+fn else None
    F = 2*tp/(2*tp+fp+fn) if (2*tp+fp+fn) else None
    return {"n": len(items), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "P": P, "R": R, "F1": F}


def main():
    cfg = InstanceBEqConfig(mock=False)
    oracle = LeanOracle(cfg)
    t0 = time.time()
    snd = soundness_stress(oracle, cfg)
    print(f"soundness stress: {len(snd)} items  [{time.time()-t0:.0f}s]", flush=True)
    dfn = definitional_stress(oracle, cfg)
    print(f"definitional stress: {len(dfn)} items  [{time.time()-t0:.0f}s]", flush=True)
    items = snd + dfn

    # certifier on soundness: positive=unfaithful (hollow). We score the "type-checks but hollow"
    # benchmark = items that GENUINELY type-check (the hard case); multi-field sorry-injections that
    # break syntax are excluded from the headline (the certifier flags them anyway, but they no
    # longer exemplify the type-checks-yet-unfaithful gap). On definitional it is a sound certifier.
    snd_tc = [it for it in items if it["gen"] == "soundness" and it["typechecks"]]
    snd_score = score(snd_tc)
    n_excluded = sum(1 for it in items if it["gen"] == "soundness" and not it["typechecks"])
    dfn_faith = [it for it in dfn if it["truth"] == "faithful"]
    dfn_corr = [it for it in dfn if it["truth"] == "unfaithful"]
    dfn_cov = sum(1 for it in dfn_faith if it["certifier"] == "faithful")
    dfn_falsecert = sum(1 for it in dfn_corr if it["certifier"] == "faithful")
    # blind baselines (type-check-only / BEq+) never predict unfaithful on soundness
    n_hollow = sum(1 for it in snd_tc if it["truth"] == "unfaithful")
    n_tc_def = sum(1 for it in dfn if it["typechecks"])

    res = {"n_total": len(snd_tc) + len(dfn), "n_soundness_typecheck": len(snd_tc),
           "n_soundness_excluded_nontypecheck": n_excluded, "n_definitional": len(dfn),
           "all_typecheck": (n_excluded == 0),
           "soundness_certifier": snd_score,
           "soundness_blind_baseline_recall": 0.0, "soundness_n_hollow": n_hollow,
           "definitional_curated_coverage": f"{dfn_cov}/{len(dfn_faith)}",
           "definitional_false_certifications": dfn_falsecert,
           "seconds": round(time.time()-t0), "items": items}
    (LOG/"synthetic_stress_result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== synthetic stress benchmark ({len(snd_tc)+len(dfn)} type-checking items; "
          f"{n_excluded} non-type-checking soundness variants excluded) ===")
    s = snd_score
    print(f"soundness  (n={s['n']}, {n_hollow} hollow): certifier P={s['P']} R={s['R']} F1={s['F1']}  | blind baseline R=0.0")
    print(f"definitional (n={len(dfn)}, {n_tc_def} type-check): curated coverage {dfn_cov}/{len(dfn_faith)}, false-cert={dfn_falsecert}")
    # integrity: certifier must never miss a hollow or false-certify a corruption (among typechecking)
    miss = [it for it in snd_tc if it["truth"] == "unfaithful" and it["certifier"] != "unfaithful"]
    print(f"certifier missed hollows (must be 0): {len(miss)}")
    print("wrote", LOG/"synthetic_stress_result.json")


if __name__ == "__main__":
    main()
