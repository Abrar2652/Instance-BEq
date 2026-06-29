"""Run baselines (A type-check, B majority-voting, C llm-judge) over a folder of artifacts.

Usage:
  python -m instance_beq.eval.run_baselines --inputs <dir> --mode {mock,real} --which A B C
Emits one summary JSON per baseline, in the same shape as run_certifier's summary so metrics.py
scores them identically.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from instance_beq.config import InstanceBEqConfig
from instance_beq.artifacts import parse_lean_file
from instance_beq.harness.lean_oracle import LeanOracle, load_mock_db
from instance_beq.harness.llm import LLMClient
from instance_beq import baselines
from instance_beq.eval.run_certifier import load_informal_map, match_informal

_BASELINE = {
    "A": ("typecheck_only", lambda art, o, l, c: baselines.baseline_typecheck_only(art, o)),
    "B": ("majority_voting", lambda art, o, l, c: baselines.baseline_majority_voting(art, l, c)),
    "C": ("llm_judge", lambda art, o, l, c: baselines.baseline_llm_judge(art, l, c)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--mode", choices=["mock", "real"], default="mock")
    ap.add_argument("--which", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
    ap.add_argument("--problem-jsonl", default=None)
    ap.add_argument("--oracle-mock-db", default="tests/mock_data/oracle_db.json")
    ap.add_argument("--llm-mock-db", default="tests/mock_data/llm_db.json")
    ap.add_argument("--outdir", default="instance_beq/eval/results")
    args = ap.parse_args()

    cfg = InstanceBEqConfig(mock=(args.mode == "mock"))
    oracle = LeanOracle(cfg, mock_db=load_mock_db(args.oracle_mock_db) if cfg.mock else None)
    llm = LLMClient(cfg, mock_db=load_mock_db(args.llm_mock_db) if cfg.mock else None)
    informal_map = load_informal_map(args.problem_jsonl)

    inputs = Path(args.inputs)
    files = [str(inputs)] if inputs.is_file() else sorted(
        glob.glob(str(inputs / "**/*.lean"), recursive=True))

    for key in args.which:
        name, fn = _BASELINE[key]
        certs = []
        for f in files:
            art = parse_lean_file(f)
            art.informal = match_informal(art, informal_map)
            r = fn(art, oracle, llm, cfg)
            # express a baseline as a single 'overall' result on the file
            certs.append({"path": f, "formal_faithful": r.verdict,
                          "results": [{**r.to_dict(), "check": "overall", "target": f}]})
        summary = {"mock": cfg.mock, "baseline": name, "n_files": len(certs),
                   "formal_verdicts": _tally([c["formal_faithful"] for c in certs]),
                   "certificates": certs}
        out = Path(args.outdir) / f"baseline_{name}_{args.mode}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[{name}] {summary['formal_verdicts']} -> {out}")


def _tally(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


if __name__ == "__main__":
    main()
