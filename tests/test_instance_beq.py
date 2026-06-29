"""Instance-BEq test suite — runs GREEN with NO Lean and NO network (pure mock mode).

Covers: parser correctness, each of the three checks' discriminating power (faithful vs hollow),
baselines, the end-to-end certifier, and the metrics mock-table guard. CI runs `pytest -q`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from instance_beq.config import InstanceBEqConfig
from instance_beq.artifacts import parse_lean_file, parse_lean_text
from instance_beq.harness.lean_oracle import LeanOracle, load_mock_db
from instance_beq.harness.llm import LLMClient
from instance_beq.checks.instance_soundness import check_instance_soundness, _field_proof_targets
from instance_beq.checks.definitional import check_definitional
from instance_beq.checks.theorem_transfer import (
    check_transfer_validity, check_statement_faithfulness,
)
from instance_beq.checks.types import Certificate
from instance_beq import baselines

ROOT = Path(__file__).resolve().parent
ART = ROOT / "mock_data" / "artifacts"
FAITHFUL = str(ART / "faithful_leastsquares.lean")
HOLLOW = str(ART / "hollow_lasso.lean")
ORACLE_DB = load_mock_db(str(ROOT / "mock_data" / "oracle_db.json"))
LLM_DB = load_mock_db(str(ROOT / "mock_data" / "llm_db.json"))


def mock_cfg(refdef_source="llm"):
    return InstanceBEqConfig(mock=True, refdef_source=refdef_source)


def oracle(cfg):
    return LeanOracle(cfg, mock_db=ORACLE_DB)


def llm(cfg):
    return LLMClient(cfg, mock_db=LLM_DB)


# --------------------------------------------------------------------------- parser
def test_parser_extracts_declarations_faithful():
    art = parse_lean_file(FAITHFUL)
    assert [d.name for d in art.defs] == ["LeastSquares_problem.f"]
    assert [d.name for d in art.instances] == ["LeastSquares_GD.Gradient_Descent"]
    assert [d.name for d in art.theorems] == ["LeastSquares_GD.gradient_method"]
    assert "Optlib.Autoformalization.Template.GD_template" in art.imports


def test_parser_extracts_declarations_hollow():
    art = parse_lean_file(HOLLOW)
    assert [d.name for d in art.defs] == ["Lasso_pro.f"]
    assert [d.name for d in art.instances] == ["Lasso_pg.pg"]
    assert [d.name for d in art.theorems] == ["Lasso_convergence"]


def test_parser_where_fields_and_proof_targets():
    art = parse_lean_file(FAITHFUL)
    inst = art.instances[0]
    assert set(["x", "t", "l", "update", "hl", "initial"]).issubset(set(inst.fields))
    # proof-bearing fields resolve to their backing lemmas; data fields are excluded
    targets = _field_proof_targets(inst)
    assert "update_cor" in targets and "pos_l" in targets
    assert "x" not in targets and "t" not in targets


def test_parser_handles_local_notation_and_sections():
    art = parse_lean_file(FAITHFUL)
    assert any("notation" in n for n in art.local_notation)
    assert "LeastSquares" in art.sections


def test_parser_pure_text_roundtrip():
    src = (
        "import Foo\n\n"
        "def g : Nat := 1\n\n"
        "instance h : C where\n  a := proofA\n  b := proofB\n\n"
        "theorem t : P := by simp\n"
    )
    art = parse_lean_text(src)
    assert [d.kind for d in art.decls] == ["def", "instance", "theorem"]
    assert art.instances[0].fields == ["a", "b"]


# --------------------------------------------------------------------------- check 2
def test_instance_soundness_passes_faithful():
    cfg = mock_cfg()
    art = parse_lean_file(FAITHFUL)
    res = check_instance_soundness(art, oracle(cfg), cfg)
    assert len(res) == 1
    assert res[0].verdict == "faithful"
    assert res[0].confidence is None  # purely symbolic


def test_instance_soundness_catches_hollow():
    cfg = mock_cfg()
    art = parse_lean_file(HOLLOW)
    res = check_instance_soundness(art, oracle(cfg), cfg)
    assert res[0].verdict == "unfaithful"
    # evidence must name the sorry-tainted field/proof
    tainted = res[0].evidence["tainted"]
    assert any("sorryAx" in v for v in sum(tainted.values(), []))


# --------------------------------------------------------------------------- check 1
def test_definitional_passes_faithful():
    cfg = mock_cfg()
    art = parse_lean_file(FAITHFUL)
    res = check_definitional(art, oracle(cfg), llm(cfg), cfg)
    assert res[0].verdict == "faithful"
    assert res[0].evidence["winning_tactic"] is not None


def test_definitional_flags_or_abstains_on_bad_def():
    cfg = mock_cfg()
    art = parse_lean_file(HOLLOW)
    res = check_definitional(art, oracle(cfg), llm(cfg), cfg)
    # ensemble exhausts; with allow_unknown default True this is a conservative 'unknown'
    assert res[0].verdict in ("unfaithful", "unknown")


def test_definitional_unknown_when_no_reference():
    cfg = mock_cfg(refdef_source="retrieval")  # retrieval not wired -> no ref -> unknown
    art = parse_lean_file(FAITHFUL)
    res = check_definitional(art, oracle(cfg), llm(cfg), cfg)
    assert res[0].verdict == "unknown"
    assert "no reference def" in res[0].evidence["reason"]


# --------------------------------------------------------------------------- check 3
def test_transfer_validity_faithful_vs_unfaithful():
    cfg = mock_cfg()
    rf = check_transfer_validity(parse_lean_file(FAITHFUL), oracle(cfg), cfg)
    rh = check_transfer_validity(parse_lean_file(HOLLOW), oracle(cfg), cfg)
    assert rf[0].verdict == "faithful"
    assert rh[0].verdict == "unfaithful"


def test_statement_faithfulness_reports_confidence():
    cfg = mock_cfg()
    rf = check_statement_faithfulness(parse_lean_file(FAITHFUL), llm(cfg), oracle(cfg), cfg)
    rh = check_statement_faithfulness(parse_lean_file(HOLLOW), llm(cfg), oracle(cfg), cfg)
    assert rf[0].verdict == "faithful" and rf[0].confidence is not None
    assert rh[0].verdict == "unfaithful"


# --------------------------------------------------------------------------- certificate
def test_formal_certificate_aggregation():
    cfg = mock_cfg()
    art = parse_lean_file(HOLLOW)
    cert = Certificate(path=HOLLOW)
    cert.results += check_instance_soundness(art, oracle(cfg), cfg)
    cert.results += check_transfer_validity(art, oracle(cfg), cfg)
    # any formal unfaithful => formal_faithful is unfaithful
    assert cert.formal_faithful == "unfaithful"


def test_formal_certificate_excludes_statement_faithfulness():
    # 3b (statement_faithfulness) must NOT be part of the formal certificate
    cfg = mock_cfg()
    art = parse_lean_file(FAITHFUL)
    cert = Certificate(path=FAITHFUL)
    cert.results += check_statement_faithfulness(art, llm(cfg), oracle(cfg), cfg)
    # only a 3b result present -> no formal checks -> unknown
    assert cert.formal_faithful == "unknown"


# --------------------------------------------------------------------------- baselines
def test_baseline_typecheck_only_is_blind_to_hollow():
    """Type-check-only passes BOTH files — including the hollow one — because `sorry` is a Lean
    warning, not an error. This blind spot is precisely what Instance-BEq exists to close, so we
    assert it explicitly: it is the experimental crux, not an incidental behavior."""
    cfg = mock_cfg()
    o = LeanOracle(cfg, mock_db=ORACLE_DB)
    rf = baselines.baseline_typecheck_only(parse_lean_file(FAITHFUL), o)
    rh = baselines.baseline_typecheck_only(parse_lean_file(HOLLOW), o)
    assert rf.verdict == "faithful"
    assert rh.verdict == "faithful"   # <-- the blind spot: hollow file type-checks
    # meanwhile instance-soundness catches the hollow one
    sound = check_instance_soundness(parse_lean_file(HOLLOW), o, cfg)
    assert sound[0].verdict == "unfaithful"


def test_baseline_llm_judge_discriminates():
    cfg = mock_cfg()
    rf = baselines.baseline_llm_judge(parse_lean_file(FAITHFUL), llm(cfg), cfg)
    rh = baselines.baseline_llm_judge(parse_lean_file(HOLLOW), llm(cfg), cfg)
    assert rf.verdict == "faithful"
    assert rh.verdict == "unfaithful"


def test_baseline_majority_voting_thresholds():
    cfg = mock_cfg()
    rf = baselines.baseline_majority_voting(parse_lean_file(FAITHFUL), llm(cfg), cfg)
    rh = baselines.baseline_majority_voting(parse_lean_file(HOLLOW), llm(cfg), cfg)
    assert rf.verdict == "faithful"
    assert rh.verdict == "unfaithful"
    assert rf.evidence["avg_score"] > rh.evidence["avg_score"]


# --------------------------------------------------------------------------- metrics guard
def test_metrics_refuses_mock_table_without_flag(tmp_path):
    from instance_beq.eval import metrics
    summary = {"mock": True, "certificates": [
        {"path": "f.lean", "formal_faithful": "unfaithful",
         "results": [{"check": "instance_soundness", "target": "I", "verdict": "unfaithful",
                      "confidence": None, "evidence": {}, "cost": {}}]}
    ]}
    sp = tmp_path / "summary.json"
    sp.write_text(json.dumps(summary), encoding="utf-8")
    pred, is_mock = metrics.predictions_from_summary(str(sp))
    assert is_mock is True
    # the CLI enforces the guard; here we assert the signal the CLI checks is present
    assert ("f.lean", "instance_soundness", "I") in pred


def test_metrics_scoring_math():
    from instance_beq.eval.metrics import score_predictions
    gold = {("a", "instance_soundness", "I"): "unfaithful",
            ("b", "instance_soundness", "J"): "faithful"}
    pred = {("a", "instance_soundness", "I"): "unfaithful",   # tp
            ("b", "instance_soundness", "J"): "unfaithful"}   # fp
    m = score_predictions(pred, gold)["instance_soundness"]
    assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 0
    assert m["precision"] == 0.5 and m["recall"] == 1.0
