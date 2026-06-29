#!/usr/bin/env python3
"""Check-2 over REGENERATED SITA outputs -> the motivating hollow-instance-rate.

For each generated .lean file: compile it, discover its `instance` declarations, and run
`#print axioms` on each to classify sound vs hollow (sorryAx / disallowed axiom in the closure).
Reports, among the files that TYPE-CHECK (0 errors), the fraction that contain >=1 hollow instance
— the headline statistic ("type-checks != faithful").

Usage:
  python scripts/certify_regen.py <dir-with-generated-lean>  [--glob '*.lean']  [--one-per-problem]
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle

INSTANCE_RE = re.compile(r"^\s*instance\s+([A-Za-z_][A-Za-z0-9_'.]*)", re.MULTILINE)


def discover_instances(text: str):
    return list(dict.fromkeys(INSTANCE_RE.findall(text)))  # ordered-unique


def classify(axset, allowed):
    if axset is None:
        return "unknown"
    if any(tok in a for a in axset for tok in SORRY_TOKENS):
        return "hollow"
    if any(a not in allowed for a in axset):
        return "hollow"          # disallowed axiom
    return "sound"


def certify_file(oracle, cfg, path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    insts = discover_instances(text)
    # append axiom probes for every instance, compile the whole file once
    probe = text + "\n\n" + "".join(f"#print axioms {n}\n" for n in insts)
    res = oracle.check_snippet(probe)
    per = []
    for n in insts:
        per.append({"instance": n, "verdict": classify(res.axioms.get(n), cfg.allowed_axioms),
                    "axioms": res.axioms.get(n)})
    hollow = [p["instance"] for p in per if p["verdict"] == "hollow"]
    return {
        "file": str(path), "compiles": res.ok, "n_errors": len(res.errors),
        "uses_sorry_warning": res.uses_sorry, "instances": per,
        "n_instances": len(insts), "hollow_instances": hollow,
        "file_has_hollow": bool(hollow),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--glob", default="*.lean")
    ap.add_argument("--one-per-problem", action="store_true",
                    help="keep only the best (compiling, fewest-hollow) file per parent dir")
    args = ap.parse_args()

    cfg = InstanceBEqConfig(mock=False)
    oracle = LeanOracle(cfg)
    files = sorted(Path(args.dir).rglob(args.glob))
    print(f"certifying {len(files)} files under {args.dir}")
    results, t0 = [], time.time()
    for f in files:
        r = certify_file(oracle, cfg, f)
        results.append(r)
        tag = ("compiles" if r["compiles"] else f"ERR({r['n_errors']})")
        hol = ",".join(r["hollow_instances"]) or "-"
        print(f"  [{tag:>10}] {f.parent.name}/{f.name:<14} inst={r['n_instances']:<2} hollow={hol}")

    if args.one_per_problem:
        best = {}
        for r in results:
            key = Path(r["file"]).parent.name
            cur = best.get(key)
            score = (r["compiles"], -len(r["hollow_instances"]), -r["n_errors"])
            if cur is None or score > cur[0]:
                best[key] = (score, r)
        results = [v[1] for v in best.values()]

    compiling = [r for r in results if r["compiles"]]
    hollow_files = [r for r in compiling if r["file_has_hollow"]]
    print("-" * 70)
    print(f"files certified            : {len(results)}")
    print(f"  type-check (0 errors)    : {len(compiling)}")
    print(f"  of those, >=1 hollow inst: {len(hollow_files)}  "
          f"({100*len(hollow_files)/max(1,len(compiling)):.1f}%  <-- HEADLINE hollow-rate)")
    print(f"wall: {time.time()-t0:.1f}s")

    out = Path(__file__).resolve().parents[1] / "eval_logs" / "certify_regen_result.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
