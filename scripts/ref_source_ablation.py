#!/usr/bin/env python3
"""Reference-source ablation for the DEFINITIONAL check (gap: how much does check-1 coverage depend
on where the reference def comes from?). Three arms, identical tactic ensemble + kernel oracle:
  * curated   -- an independently-authored canonical RHS per problem type (domain knowledge,
                 written in a deliberately different surface form so the proof is non-trivial).
  * fewshot   -- the served LLM generates the RHS, prompted with 2 notation exemplars.
  * zeroshot  -- the served LLM generates the RHS with no exemplars (= certifier_all_checks arm).
Mechanism (all arms): inject  `example : <target> self arg = <RHS> := by <tac>`  RIGHT AFTER the
target def so it shares the def's exact scope, and discharge with an ordered tactic ensemble.
A proved equality => faithful (kernel-sound, precision 1). Not proved => abstain. We also log the
winning ensemble index, which yields the tactic-ensemble SIZE sweep (coverage@k) for free.
Out: eval_logs/ref_source_ablation_result.json
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig
from instance_beq.harness.lean_oracle import LeanOracle
from openai import OpenAI

cfg = InstanceBEqConfig(mock=False)
oracle = LeanOracle(cfg)
ext = json.loads(Path(cfg.api_config_path).read_text())
client = OpenAI(api_key=ext["api_key"], base_url=ext["base_url"])
MODEL = "qwen2.5-7b-instruct"
ANN = Path(__file__).resolve().parents[1] / "instance_beq/annotation"
LOG = Path(__file__).resolve().parents[1] / "eval_logs"

# ordered tactic ensemble (the SIZE sweep reads winning index against this order)
TACS = ["unfold {t}; ring", "unfold {t}; dsimp only; ring", "unfold {t}; simp only []; ring",
        "unfold {t}; rfl", "simp only [{t}]; ring"]

# curated independent canonical RHS per target (arg-name, RHS expression in scope's notation)
CURATED = {
    "LeastSquares_problem.f": ("x", "‖A *ᵥ x - b‖₂ ^ 2 / 2"),
    "Lasso_problem.f":        ("x", "‖A *ᵥ x - b‖₂ ^ 2 / 2"),
    "Lasso_problem.g":        ("x", "‖x‖₁ * mu"),
    "Lasso_problem.target":   ("x", "self.g x + self.f x"),
    "Lasso.f₁":               ("x", "‖A *ᵥ x - b‖₂ ^ 2 / 2"),
    "Lasso.f₂":               ("x", "‖x‖₁ * μ"),
    "JointSparseCoding_problem.f": ("x", "‖x‖₁ * lambda1"),
    "JointSparseCoding_problem.g": ("y", "‖y‖₁ * lambda2"),
    "JointSparseCoding_problem.H": ("z", "‖A *ᵥ z.1 + B *ᵥ z.2 - b‖₂ ^ 2 / 2"),
    "JointSparseCoding_problem.ψ": ("z", "self.H z + self.f z.1 + self.g z.2"),
    "Ridge_regression_problem.f":  ("x", "lam_ / 2 * ‖x‖₂ ^ 2 + ‖A *ᵥ x - b‖₂ ^ 2 / 2"),
}

FEWSHOT = (
    "Examples of the file's Lean 4 notation:\n"
    "  least-squares objective  ½‖Ax−b‖²  ->  ‖A *ᵥ x - b‖₂ ^ 2 / 2\n"
    "  ℓ1 penalty  μ‖x‖₁        ->  ‖x‖₁ * mu\n")


def llm(prompt, max_tokens=160):
    r = client.chat.completions.create(model=MODEL, temperature=0.0, max_tokens=max_tokens,
                                       messages=[{"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip()


def strip_fence(s):
    s = re.sub(r"^```[a-z0-9]*\n?", "", s.strip())
    return re.sub(r"\n?```$", "", s).strip()


def sig_of(src, target):
    """(class_binder_renamed_self, arg_type) parsed from `def <target> <binder> : <ArgT> -> ℝ :=`."""
    m = re.search(rf"\bdef\s+{re.escape(target)}\b(.*?):=", src, re.DOTALL)
    if not m:
        return None, None
    sig = m.group(1).strip()
    # binder is the first (...) group; return type is after the LAST top-level ` : `
    mb = re.match(r"\((.*?)\)\s*:\s*(.+)", sig, re.DOTALL)
    if not mb:
        return None, None
    binder = mb.group(1).strip()
    cls = binder.split(":", 1)[1].strip() if ":" in binder else binder
    rett = mb.group(2).strip()
    argt = rett.rsplit("→", 1)[0].strip() if "→" in rett else rett.split("->")[0].strip()
    return cls, argt


def inject_after_def(src, target, example):
    m = re.search(rf"(\bdef\s+{re.escape(target)}\b.*?:=)", src, re.DOTALL)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"\n(?=(?:noncomputable\s+)?(?:def|instance|theorem|lemma|class|variable|end|open|section)\b)", src[start:])
    ins = start + (nxt.start() if nxt else len(src[start:]))
    return src[:ins] + "\n\n" + example + "\n" + src[ins:]


def try_prove(src, target, cls, argt, arg, rhs, ntac=None):
    """Return winning tactic index (0-based) or None."""
    for i, tac in enumerate(TACS[:ntac] if ntac else TACS):
        ex = (f"example (self : {cls}) ({arg} : {argt}) :\n"
              f"    {target} self {arg} = {rhs} := by\n  {tac.format(t=target)}")
        snip = inject_after_def(src, target, ex)
        if snip is None:
            return None
        res = oracle.check_snippet(snip)
        if res.ok and not res.errors:
            return i
    return None


def main():
    gold = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"gold.jsonl").read_text().splitlines() if l.strip()}
    items = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"pool/items.jsonl").read_text().splitlines() if l.strip()}
    defs = [(iid, g) for iid, g in gold.items() if g["check"] == "definitional"]

    out, t0 = [], time.time()
    for iid, g in defs:
        it = items[iid]; src = it["lean_source"]; target = g["target"]
        cls, argt = sig_of(src, target)
        rec = {"id": iid, "gold": g["label"], "target": target}
        if cls is None:
            rec.update({"curated": None, "fewshot": None, "zeroshot": None, "note": "no sig"})
            out.append(rec); continue

        # arm 1: curated
        arg, rhs = CURATED.get(target, (None, None))
        widx = try_prove(src, target, cls, argt, arg, rhs) if rhs else None
        rec["curated"] = {"verdict": "faithful" if widx is not None else None, "win_idx": widx, "rhs": rhs}

        # arms 2,3: LLM-generated RHS (fewshot / zeroshot). The coverage question is about FAITHFUL
        # defs (can the LLM produce a provable reference?); run LLM arms on faithful items only,
        # with a trimmed 3-tactic ensemble (corrupted items would only ever abstain).
        for arm, shots in (("fewshot", FEWSHOT), ("zeroshot", "")):
            if g["label"] != "faithful":
                rec[arm] = {"verdict": None, "win_idx": None, "rhs": "(skipped: corrupted)"}
                continue
            prompt = (f"Write ONLY the Lean 4 expression (right-hand side, in terms of the bound "
                      f"argument) that the function `{target}` should equal, encoding this objective. "
                      f"Use the file's notations (‖·‖₂, ‖·‖₁, *ᵥ). Output just the expression.\n\n{shots}"
                      f"Objective:\n{str(it['informal'])[:700]}")
            body = strip_fence(llm(prompt))
            arg_l = (arg or "x")
            widx2 = (try_prove(src, target, cls, argt, arg_l, body, ntac=3)
                     if body and len(body) < 300 and "def" not in body else None)
            rec[arm] = {"verdict": "faithful" if widx2 is not None else None, "win_idx": widx2,
                        "rhs": body[:80]}
        out.append(rec)
        cv = lambda a: ("PROVED@%d" % rec[a]["win_idx"]) if rec[a] and rec[a]["verdict"] else "abstain"
        print(f"  {iid} {g['label']:<11} cur={cv('curated'):<11} few={cv('fewshot'):<11} zero={cv('zeroshot')}", flush=True)

    # ---- summaries -------------------------------------------------------------------------
    faith = [r for r in out if r["gold"] == "faithful"]
    corr = [r for r in out if r["gold"] == "unfaithful"]
    summary = {}
    for arm in ("curated", "fewshot", "zeroshot"):
        cov = sum(1 for r in faith if r.get(arm) and r[arm]["verdict"] == "faithful")
        falsecert = sum(1 for r in corr if r.get(arm) and r[arm]["verdict"] == "faithful")
        # coverage@k from winning indices (curated arm primarily)
        idxs = [r[arm]["win_idx"] for r in faith if r.get(arm) and r[arm]["verdict"] == "faithful"]
        covk = [sum(1 for w in idxs if w <= k) for k in range(len(TACS))]
        summary[arm] = {"faithful_coverage": f"{cov}/{len(faith)}", "coverage": round(cov/len(faith), 3),
                        "false_certifications": falsecert, "coverage_at_k": covk}
    res = {"items": out, "summary": summary, "n_faithful": len(faith), "n_corrupted": len(corr),
           "tactic_ensemble": TACS, "seconds": round(time.time()-t0)}
    (LOG/"ref_source_ablation_result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n=== reference-source ablation (definitional coverage) ===")
    for arm, s in summary.items():
        print(f"  {arm:<9} coverage={s['faithful_coverage']:<7} ({s['coverage']:.2f})  "
              f"false-cert={s['false_certifications']}  cov@k={s['coverage_at_k']}")
    print(f"\nwrote {LOG/'ref_source_ablation_result.json'}  [{res['seconds']}s]")


if __name__ == "__main__":
    main()
