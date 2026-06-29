"""Regenerate the mock oracle/LLM DBs from the fixture artifacts.

The mock fixtures must return verdicts keyed by the EXACT snippet/prompt tags the checks generate.
Those tags depend on code (e.g. the tactic-id hash), so hand-maintaining them is fragile. This
script derives every tag by importing the checks and writing a DB that, by construction, makes:

  - faithful_leastsquares.lean  -> faithful on all three checks
  - hollow_lasso.lean           -> unfaithful (hollow instance + bad def + mis-stated theorem)

Run after any change to the checks' tag scheme:
    python scripts/make_mock_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instance_beq.artifacts import parse_lean_file
from instance_beq.config import InstanceBEqConfig
from instance_beq.checks.definitional import _tac_id

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "tests" / "mock_data" / "artifacts"
OUT_ORACLE = ROOT / "tests" / "mock_data" / "oracle_db.json"
OUT_LLM = ROOT / "tests" / "mock_data" / "llm_db.json"

CLEAN_AX = ["propext", "Classical.choice", "Quot.sound"]
SORRY_AX = ["propext", "Classical.choice", "sorryAx"]

# Ground-truth design of the two fixtures: which artifact is faithful on which check.
DESIGN = {
    "faithful_leastsquares.lean": {
        "instance_faithful": True,   # instance fields proven by real lemmas (update_cor, pos_l)
        "def_faithful": True,        # def f provably equals reference
        "def_winning_tactic_index": 1,  # 'simp only [...]' closes it
        "transfer_faithful": True,   # apply abstract lemma closes the goal
        "stmt_faithful": True,
    },
    "hollow_lasso.lean": {
        "instance_faithful": False,  # field `update := self.bad_update_lemma` -> sorryAx
        "def_faithful": False,       # def f does NOT match the Lasso objective (ensemble fails)
        "def_winning_tactic_index": None,
        "transfer_faithful": False,  # apply fails: rate constant mismatch
        "stmt_faithful": False,      # O(1/k) stated where O(1/k) of wrong constant
    },
}


def build():
    cfg = InstanceBEqConfig(mock=True, refdef_source="llm")
    oracle_db: dict = {}
    llm_db: dict = {}

    for fname, design in DESIGN.items():
        art = parse_lean_file(str(ART / fname))

        # ---- file-level oracle fixture (baseline A: type-check-only) ----
        # type-check-only is INTENTIONALLY weak: the hollow file compiles fine (sorry is a
        # warning, not an error), so type-check passes it. That is the baseline's blind spot and
        # exactly what Instance-BEq exists to catch.
        from instance_beq.harness.lean_oracle import LeanOracle as _LO
        text = (ART / fname).read_text(encoding="utf-8")
        file_key = _LO._tag(text)
        if design["instance_faithful"]:
            oracle_db[file_key] = {"ok": True, "errors": [], "warnings": [],
                                   "uses_sorry": False, "axioms": {}}
        else:
            # compiles (ok=True) but emits the sorry warning; type-check-only ignores warnings.
            oracle_db[file_key] = {"ok": True, "errors": [],
                                   "warnings": [{"line": 1, "column": 0,
                                                 "message": "declaration uses 'sorry'"}],
                                   "uses_sorry": True, "axioms": {}}
        for inst in art.instances:
            if design["instance_faithful"]:
                axioms = {inst.name: CLEAN_AX}
                # add clean axioms for each proof target
                from instance_beq.checks.instance_soundness import _field_proof_targets
                for tgt in _field_proof_targets(inst):
                    axioms[tgt] = ["propext"]
                oracle_db[f"soundness_{inst.name}"] = {
                    "ok": True, "errors": [], "warnings": [],
                    "uses_sorry": False, "axioms": axioms,
                }
            else:
                from instance_beq.checks.instance_soundness import _field_proof_targets
                axioms = {inst.name: SORRY_AX}
                for tgt in _field_proof_targets(inst):
                    axioms[tgt] = ["propext", "sorryAx"]
                oracle_db[f"soundness_{inst.name}"] = {
                    "ok": True, "errors": [],
                    "warnings": [{"line": 1, "column": 0,
                                  "message": "declaration uses 'sorry'"}],
                    "uses_sorry": True, "axioms": axioms,
                }

        # ---- check 1: definitional (refdef LLM prompt + per-tactic defeq oracle keys) ----
        for d in art.defs:
            llm_db[f"refdef_{d.name}"] = (
                f"```lean\ndef {d.name}_ref := <reference for {d.name}>\n```"
            )
            win = design["def_winning_tactic_index"]
            for i, t in enumerate(cfg.tactic_ensemble):
                tag = f"defeq_{d.name}_{_tac_id(t)}"
                ok = (win is not None and i == win)
                # tactics before the winner fail; the winner closes; after winner irrelevant
                oracle_db[tag] = {
                    "ok": bool(ok), "errors": ([] if ok else
                        [{"line": 3, "column": 0, "message": "unsolved goals"}]),
                    "warnings": [], "uses_sorry": False, "axioms": {},
                }

        # ---- check 3a: transfer validity (transfer_<thm> oracle keys) ----
        for th in art.theorems:
            if design["transfer_faithful"]:
                oracle_db[f"transfer_{th.name}"] = {
                    "ok": True, "errors": [], "warnings": [],
                    "uses_sorry": False, "axioms": {},
                }
            else:
                oracle_db[f"transfer_{th.name}"] = {
                    "ok": False,
                    "errors": [{"line": 2, "column": 2,
                                "message": "apply failed: rate constant mismatch"}],
                    "warnings": [], "uses_sorry": False, "axioms": {},
                }

        # ---- check 3b: statement faithfulness (stmtfaith_<thm> LLM judge JSON) ----
        for th in art.theorems:
            verdict = design["stmt_faithful"]
            llm_db[f"stmtfaith_{th.name}"] = json.dumps({
                "faithful": bool(verdict),
                "confidence": 0.92 if verdict else 0.88,
                "reason": ("statement matches informal rate and hypotheses" if verdict
                           else "convergence rate constant disagrees with informal claim"),
            })

        # ---- baselines: llm_judge (judge_<filekey>) + majority_voting (mv_<filekey>_<i>) ----
        from instance_beq.baselines import _file_key
        fk = _file_key(art.path)
        overall = (design["instance_faithful"] and design["def_faithful"]
                   and design["transfer_faithful"])
        llm_db[f"judge_{fk}"] = json.dumps({
            "faithful": bool(overall),
            "confidence": 0.9 if overall else 0.85,
            "reason": "holistic judgement",
        })
        for i in range(16):
            llm_db[f"mv_{fk}_{i}"] = "82" if overall else "41"

    OUT_ORACLE.write_text(json.dumps(oracle_db, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_LLM.write_text(json.dumps(llm_db, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_ORACLE}  ({len(oracle_db)} keys)")
    print(f"wrote {OUT_LLM}  ({len(llm_db)} keys)")


if __name__ == "__main__":
    build()
