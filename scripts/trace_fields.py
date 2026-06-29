#!/usr/bin/env python3
"""Per-field tracing for check 2: for a hollow bridging instance, name WHICH condition field's
proof term is sorry-tainted (not just the instance).

Resolves each `field := rhs` of an `instance ... where` block to the named lemma it references,
then runs `#print axioms <lemma>` and classifies. Reuses the real LeanOracle.

Run:  python scripts/trace_fields.py
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle

# data fields carry values, not proof obligations — exempt from the sorry check
DATA_FIELDS = {"x", "y", "u", "z", "c", "d", "t", "l", "ρ", "τ",
               "x0", "y0", "u0", "x₀", "y₀", "u₀"}

TARGETS = [  # (module suffix, bridging instance name)
    ("ADMM_example", "Lasso_ADMM.toADMM"),
    ("BCD_example",  "BCD_JointSparse.BCD"),
    ("GD_example",   "LeastSquares_GD.Gradient_Descent"),  # control: all sound
]


def parse_instance(text: str, inst_name: str):
    """Return (binder, class_name, [(field, rhs), ...]) for `instance <inst_name> (binder:Class..) .. where`."""
    # find the instance header
    m = re.search(rf"instance\s+{re.escape(inst_name)}\s*\(([^:]+):\s*([A-Za-z0-9_'.]+)[^)]*\)",
                  text)
    binder, cls = (m.group(1).strip(), m.group(2).strip()) if m else (None, None)
    # capture the where-block: from `where` after the instance header to the next top-level decl
    hm = re.search(rf"instance\s+{re.escape(inst_name)}\b.*?\bwhere\b", text, re.DOTALL)
    fields = []
    if hm:
        rest = text[hm.end():]
        for line in rest.splitlines():
            if re.match(r"^\S", line) and ":=" not in line:  # next top-level decl ends the block
                break
            fm = re.match(r"\s+([A-Za-z_][A-Za-z0-9_'₀₁₂₃]*)\s*:=\s*(.+)$", line)
            if fm:
                fields.append((fm.group(1), fm.group(2).strip()))
    return binder, cls, fields


def resolve_lemma(rhs: str, binder: str, cls: str):
    """Resolve the proof-term lemma a field references."""
    # `binder.foo`  ->  Class.foo
    m = re.match(rf"{re.escape(binder)}\.([A-Za-z0-9_'₀₁₂₃]+)", rhs)
    if m and cls:
        return f"{cls}.{m.group(1)}"
    # `fun ... ↦ Cap.dotted ...`  or bare `Cap.dotted`  -> first dotted Capitalized identifier
    m = re.search(r"([A-Z][A-Za-z0-9_']*\.[A-Za-z0-9_'.]+)", rhs)
    if m:
        return m.group(1)
    return None  # inline `by ...` / data literal — not a named lemma


def main():
    cfg = InstanceBEqConfig(mock=False)
    oracle = LeanOracle(cfg)
    lean_root = cfg.lean_cwd
    out = {}
    t0 = time.time()

    for mod_suffix, inst in TARGETS:
        text = (lean_root / "Optlib/Autoformalization/Example" / f"{mod_suffix}.lean").read_text("utf-8")
        binder, cls, fields = parse_instance(text, inst)
        print(f"\n=== {mod_suffix} :: {inst}   (binder {binder} : {cls}) ===")
        # build one snippet that prints axioms for every resolved condition-field lemma
        cond = [(f, resolve_lemma(rhs, binder, cls)) for f, rhs in fields if f not in DATA_FIELDS]
        lemmas = sorted({lm for _, lm in cond if lm})
        mod = f"Optlib.Autoformalization.Example.{mod_suffix}"
        src = f"import {mod}\n" + "".join(f"#print axioms {lm}\n" for lm in lemmas)
        res = oracle.check_snippet(src)

        rows = []
        for f, lm in cond:
            if lm is None:
                verdict, axset = "inline/data", None
            else:
                axset = res.axioms.get(lm)
                if axset is None:
                    verdict = "unresolved"
                elif any(tok in a for a in axset for tok in SORRY_TOKENS):
                    verdict = "SORRY-TAINTED"
                elif any(a not in cfg.allowed_axioms for a in axset):
                    verdict = "bad-axiom"
                else:
                    verdict = "clean"
            rows.append({"field": f, "lemma": lm, "verdict": verdict, "axioms": axset})
            mark = {"clean": "✓", "SORRY-TAINTED": "✗", "bad-axiom": "✗"}.get(verdict, "·")
            print(f"  {mark} {f:<10} -> {str(lm):<34} {verdict}")
        tainted = [r["field"] for r in rows if r["verdict"] in ("SORRY-TAINTED", "bad-axiom")]
        print(f"  hollow condition fields: {tainted or 'none'}")
        out[mod_suffix] = {"instance": inst, "fields": rows, "tainted_fields": tainted}

    p = Path(__file__).resolve().parents[1] / "eval_logs" / "trace_fields_result.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    print(f"\nwrote {p}   (wall {time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
