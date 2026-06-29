"""Main entry: certify a folder of SITA output artifacts.

Usage:
  python -m instance_beq.eval.run_certifier --inputs <dir-or-file> --mode {mock,real}
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

from instance_beq.config import InstanceBEqConfig
from instance_beq.artifacts import parse_lean_file
from instance_beq.harness.lean_oracle import LeanOracle, load_mock_db
from instance_beq.harness.llm import LLMClient
from instance_beq.checks.instance_soundness import check_instance_soundness
from instance_beq.checks.definitional import check_definitional
from instance_beq.checks.theorem_transfer import (
    check_transfer_validity, check_statement_faithfulness,
)
from instance_beq.checks.types import Certificate


def load_informal_map(problem_jsonl: str | None) -> dict:
    if not problem_jsonl or not Path(problem_jsonl).exists():
        return {}
    out = {}
    for line in Path(problem_jsonl).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out[rec.get("problem_name", "")] = rec
    return out


def match_informal(art, informal_map: dict) -> dict | None:
    # naive match by problem_name substring in path; the implementation can improve the mapping.
    base = os.path.basename(art.path).lower()
    for name, rec in informal_map.items():
        if name and name.lower().split()[0] in base:
            return rec
    return None


def certify_file(path: str, oracle, llm, cfg, informal_map) -> Certificate:
    art = parse_lean_file(path)
    art.informal = match_informal(art, informal_map)
    cert = Certificate(path=path)
    cert.results += check_instance_soundness(art, oracle, cfg)
    cert.results += check_definitional(art, oracle, llm, cfg)
    cert.results += check_transfer_validity(art, oracle, cfg)
    cert.results += check_statement_faithfulness(art, llm, oracle, cfg)
    return cert


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True, help="dir of .lean artifacts or a single file")
    ap.add_argument("--mode", choices=["mock", "real"], default="mock")
    ap.add_argument("--problem-jsonl", default=None)
    ap.add_argument("--oracle-mock-db", default="tests/mock_data/oracle_db.json")
    ap.add_argument("--llm-mock-db", default="tests/mock_data/llm_db.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--refdef-source", default="retrieval",
                    choices=["retrieval", "llm", "property"])
    args = ap.parse_args()

    cfg = InstanceBEqConfig(mock=(args.mode == "mock"), refdef_source=args.refdef_source)
    oracle_db = load_mock_db(args.oracle_mock_db) if cfg.mock else None
    llm_db = load_mock_db(args.llm_mock_db) if cfg.mock else None
    oracle = LeanOracle(cfg, mock_db=oracle_db)
    llm = LLMClient(cfg, mock_db=llm_db)
    informal_map = load_informal_map(args.problem_jsonl)

    inputs = Path(args.inputs)
    files = [str(inputs)] if inputs.is_file() else sorted(glob.glob(str(inputs / "**/*.lean"),
                                                                     recursive=True))
    certs = [certify_file(f, oracle, llm, cfg, informal_map) for f in files]

    summary = {
        "mock": cfg.mock,
        "n_files": len(certs),
        "formal_verdicts": _tally([c.formal_faithful for c in certs]),
        "certificates": [c.to_dict() for c in certs],
    }
    out = args.out or f"instance_beq/eval/results/summary_{args.mode}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("mock", "n_files", "formal_verdicts")}, indent=2))
    print(f"wrote {out}")


def _tally(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


if __name__ == "__main__":
    main()
