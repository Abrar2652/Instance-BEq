#!/usr/bin/env python3
"""Build the BLINDED human-correlation annotation pool (HUMAN_CORRELATION_STUDY.md §6).

Output (under instance_beq/annotation/pool/):
  items.jsonl   -- one blinded item per (file, check, target). Opaque id (IT####), the
                   sanitized Lean source inlined, the matched informal spec, and (for
                   transfer/statement) the abstract template theorem. NO file path, NO
                   provenance, NO ground truth.  THIS is what annotators A1/A2 see.
  keymap.json   -- PRIVATE: id -> {path, source_bucket, provenance, construction_truth,
                   note}. Used ONLY by the adjudicator / integrity gate. Never shown to A1/A2.

"Source buckets" (HUMAN_CORRELATION_STUDY.md §2):
  gold     -- the released Example/*.lean anchors (mostly faithful; known-hollow ADMM/BCD)
  planted  -- ground-truth-by-construction faults: sorry-injection (check 2) + corrupted
              reference defs (check 1) + the scratch hollow/wrongrate variants
  regen    -- realistic regenerated SITA outputs (the representative bulk)
  mock     -- the hand-built faithful/hollow fixtures

Blinding: the annotator sees only the sanitized Lean text + informal spec; provenance-revealing
comments (`-- PLANTED HOLLOW`, `#print axioms`, chat-template leakage, `expect:` markers) are
stripped, and items are shuffled with a fixed seed so order carries no signal.

Run:  python scripts/build_annotation_pool.py
"""
from __future__ import annotations
import json, random, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from instance_beq.artifacts import parse_lean_text, parse_lean_file  # noqa: E402

LEAN = ROOT / "Code/lean/Optlib/Autoformalization"
MOCK = ROOT / "tests/mock_data/artifacts"
PROBLEMS = [ROOT / "Code/data/problem/problem_test.jsonl",
            ROOT / "Code/data/problem/problem_gd.jsonl"]
OUT = ROOT / "instance_beq/annotation/pool"

# ---------------------------------------------------------------- informal specs
def load_specs() -> dict[tuple[str, str], dict]:
    d = {}
    for p in PROBLEMS:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            d[(r["problem_name"], r["class"])] = r
    return d

SPECS = load_specs()

def spec(name: str, cls: str) -> dict:
    r = SPECS[(name, cls)]
    return {"problem_name": r["problem_name"], "class": r["class"],
            "problem_statement": r["problem_statement"], "algorithm": r["algorithm"]}

# ---------------------------------------------------------------- sanitisation
_LEAK = re.compile(r"^\s*(user|assistant|system)\s*$", re.I)
_FENCE = re.compile(r"^\s*```")
_CONTINUE = re.compile(r"^\s*Continue from where you left off", re.I)
_GIVEAWAY = re.compile(r"(PLANTED|HOLLOW|must be caught|expect:|HEADLINE|sorry-free|"
                       r"<--|ground truth|known[- ]hollow)", re.I)

def sanitize(text: str) -> str:
    """Strip provenance-revealing noise so the annotator judges the math, not the metadata."""
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#print axioms"):
            continue
        if _LEAK.match(ln) or _FENCE.match(ln) or _CONTINUE.match(ln):
            continue
        # drop trailing giveaway comments but keep the code on the line
        if "--" in ln and _GIVEAWAY.search(ln.split("--", 1)[1]):
            ln = ln.split("--", 1)[0].rstrip()
            if not ln:
                continue
        # collapse pathologically long single lines (degenerate hallucinated tactic blocks),
        # but NEVER hide a `sorry`/`admit` (the soundness signal).
        if len(ln) > 300 and not re.search(r"\bsorry\b|\badmit\b|sorryAx", ln):
            ln = ln[:160].rstrip() + " … [long line truncated — repetitive tactic block]"
        out.append(ln)
    # collapse 3+ blank lines
    txt = "\n".join(out)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip() + "\n"

def truncate_long_bodies(text: str, max_lines: int = 45) -> str:
    """Replace pathologically long proof bodies (no sorry inside) with a marker, so the
    file stays readable. Decls containing sorry/admit are NEVER truncated (soundness signal)."""
    art = parse_lean_text(text)
    lines = text.splitlines()
    cuts = []  # (start0, end0, header_keep_upto0)
    for d in art.decls:
        s, e = d.span[0] - 1, d.span[1]  # span is (1-indexed start, exclusive-ish end)
        block = lines[s:e]
        if len(block) <= max_lines:
            continue
        if re.search(r"\bsorry\b|\badmit\b|sorryAx", "\n".join(block)):
            continue  # keep — carries the soundness signal
        # find first body line (after := or where) to keep signature + a few lines
        keep = s
        for i in range(s, e):
            if ":=" in lines[i] or re.search(r"\bwhere\b", lines[i]):
                keep = i
                break
        cuts.append((s, e, keep))
    if not cuts:
        return text
    cuts.sort()
    res, prev = [], 0
    for (s, e, keep) in cuts:
        res.extend(lines[prev:keep + 1])
        res.append(f"  -- [proof body of {e - keep - 1} lines omitted; contains no `sorry`]")
        prev = e
    res.extend(lines[prev:])
    return "\n".join(res) + "\n"

# ---------------------------------------------------------------- template theorems (transfer ref)
def slice_decl_from_file(path: Path, name: str, sig_only: bool = True) -> str:
    art = parse_lean_file(path)
    for d in art.decls:
        if d.name == name:
            raw = d.raw
            if sig_only:
                # keep up to the first ':= by' / ':=' so we show the STATEMENT not the proof
                m = re.search(r":=\s*by\b", raw)
                if m:
                    raw = raw[:m.start()].rstrip()
                elif ":=" in raw:
                    raw = raw[:raw.index(":=")].rstrip()
            return raw
    return f"-- (abstract theorem {name} not found in {path.name})"

TEMPLATE = LEAN / "Template"
ABSTRACT = {
    "GD":   ("GD_template.lean",            "gradient_method_convergence"),
    "PGD":  ("PGD_template.lean",           "proximal_gradient_converge"),
    "ADMM": ("ADMM_template.lean",          "admm_converges"),
    "BCD":  ("BCD_template.lean",           "Sufficient_Descent1"),
}
def abstract_thm(fam: str) -> str:
    f, n = ABSTRACT[fam]
    return slice_decl_from_file(TEMPLATE / f, n, sig_only=True)

# ---------------------------------------------------------------- pool assembly
ITEMS = []          # blinded (what annotators see)
KEY = {}            # private
_counter = [0]

def add(*, lean_text: str, check: str, target: str, informal: dict,
        source_bucket: str, path: str, provenance: str, truth: str | None,
        note: str = "", fam: str | None = None):
    _counter[0] += 1
    iid = f"IT{_counter[0]:04d}"
    item = {
        "id": iid,
        "check": check,                      # definitional|instance_soundness|transfer_validity|statement_faithfulness
        "target": target,
        "informal": informal,
        "lean_source": truncate_long_bodies(sanitize(lean_text)),
    }
    if check in ("transfer_validity", "statement_faithfulness") and fam:
        item["abstract_theorem"] = abstract_thm(fam)
    ITEMS.append(item)
    KEY[iid] = {"path": path, "source_bucket": source_bucket, "provenance": provenance,
                "construction_truth": truth, "check": check, "target": target, "note": note}

# ============================================================ 1) GOLD ANCHORS
def gold_anchor(relpath, fam, pname, cls, targets, provenance):
    p = LEAN / relpath
    text = p.read_text(encoding="utf-8")
    sp = spec(pname, cls)
    for (check, target, truth, note) in targets:
        add(lean_text=text, check=check, target=target, informal=sp,
            source_bucket="gold", path=relpath, provenance=provenance,
            truth=truth, note=note, fam=fam)

gold_anchor("Example/GD_example.lean", "GD", "Least squares problem", "gradient descent", [
    ("definitional", "LeastSquares_problem.f", "faithful", "f = 1/2 ||Ax-b||^2 matches informal"),
    ("instance_soundness", "LeastSquares_GD.Gradient_Descent", "faithful",
     "all condition fields proven by real lemmas (update_cor, pos_l, ht) — no sorry"),
    ("statement_faithfulness", "LeastSquares_GD.gradient_method", "faithful",
     "O(1/k) rate 1/(2(k+1)t) matches the GD descent bound"),
    ("transfer_validity", "LeastSquares_GD.gradient_method", "faithful",
     "obtained by apply gradient_method_convergence to the instance"),
], "Optlib GD gold example (released)")

gold_anchor("Example/PGD_example.lean", "PGD", "Lasso problem", "proximal gradient", [
    ("definitional", "Lasso_problem.f", "faithful", "smooth part 1/2||Ax-b||^2"),
    ("definitional", "Lasso_problem.g", "faithful", "nonsmooth part mu*||x||_1"),
    ("definitional", "Lasso_problem.target", "faithful", "f + g = full Lasso objective"),
    ("instance_soundness", "proximal_gradient_method_Lasso.proximal_gradient_method", "faithful",
     "update field = update_cor, a REAL proof via norm_one_proximal — genuinely sound"),
    ("statement_faithfulness", "Lasso_convergence", "faithful", "O(1/k) ergodic rate, target gap"),
    ("transfer_validity", "Lasso_convergence", "faithful", "apply proximal_gradient_converge"),
], "Optlib PGD gold example (released)")

gold_anchor("Example/ADMM_example.lean", "ADMM", "Lasso problem with variable splitting", "ADMM", [
    ("definitional", "Lasso.f₁", "faithful", "1/2||Ax-b||^2"),
    ("definitional", "Lasso.f₂", "faithful", "mu*||x||_1"),
    ("instance_soundness", "Lasso.isProblem", "faithful",
     "data-bundling Problem instance, no proof-obligation fields"),
    ("instance_soundness", "Lasso_ADMM.toADMM", "unfaithful",
     "HOLLOW: iter₁/iter₂/iter₃ <- iter_cor1/2/3 and hX/hY <- uniq_subX/uniq_subY are ALL sorry"),
    ("instance_soundness", "isConvexKKT.isLasso_KKT", "unfaithful",
     "HOLLOW: subgrad₁/subgrad₂/eq <- isLasso_KKT₁/₂/₃ are ALL sorry"),
    ("statement_faithfulness", "lasso_ADMM_converges", "faithful",
     "convergence to a KKT point of the Lasso — matches claim"),
    ("transfer_validity", "lasso_ADMM_converges", "faithful",
     "apply admm_converges; structurally valid specialization (rests on sorry feasible/slater)"),
], "Optlib ADMM gold example (released; canonical hollow instances)")

gold_anchor("Example/BCD_example.lean", "BCD", "Joint sparse coding", "BCD", [
    ("definitional", "JointSparseCoding_problem.f", "faithful", "lambda1*||x||_1 (x-block nonsmooth)"),
    ("definitional", "JointSparseCoding_problem.g", "faithful", "lambda2*||y||_1 (y-block nonsmooth)"),
    ("definitional", "JointSparseCoding_problem.H", "faithful", "1/2||Ax+By-b||^2 smooth coupling"),
    ("definitional", "JointSparseCoding_problem.ψ", "faithful", "f+g+H total objective"),
    ("instance_soundness", "JointSparseCoding_problem.ProblemData", "unfaithful",
     "HOLLOW: conH/lpos/lip fields are sorry (lbdf/lbdg/hf/hg are real)"),
    ("instance_soundness", "BCD_JointSparse.BCD", "unfaithful",
     "HOLLOW: s₁/s₂ <- update_cor1/update_cor2 are sorry"),
    ("statement_faithfulness", "JointSparse_Sufficient_Descent1", "faithful",
     "sufficient-descent inequality, valid BCD property"),
], "Optlib BCD gold example (released; hollow instances)")

# ============================================================ 2) REGEN BULK
def regen(relpath, fam, pname, cls, targets, provenance):
    p = LEAN / relpath
    text = p.read_text(encoding="utf-8")
    sp = spec(pname, cls)
    for (check, target, truth, note) in targets:
        add(lean_text=text, check=check, target=target, informal=sp,
            source_bucket="regen", path=relpath, provenance=provenance, truth=truth, note=note, fam=fam)

regen("Regen_gd/Least_squares_problem_gradient_descent/Trial1.lean", "GD",
      "Least squares problem", "gradient descent", [
    ("definitional", "LeastSquares_problem.f", "faithful", "1/2||Ax-b||^2 — correct"),
    ("instance_soundness", "LeastSquares_GD.Gradient_Descent", "faithful", "no sorry; real lemmas"),
    ("statement_faithfulness", "LeastSquares_GD.gradient_method", "faithful", "O(1/k)"),
], "regenerated SITA output; post-cutoff: unknown")

regen("Regen_gd/Ridge_regression_gradient_descent/Trial1.lean", "GD",
      "Ridge regression", "gradient descent", [
    ("definitional", "Ridge_regression_problem.f", "faithful",
     "1/2||Ax-b||^2 + lam/2||x||^2 — matches informal"),
    ("instance_soundness", "Ridge_regression_GD.Gradient_Descent", "faithful",
     "no sorry; fields = real lemmas (file has chat-leak noise / may not compile, but no sorry)"),
    ("statement_faithfulness", "Ridge_regression_GD.gradient_method", "faithful", "O(1/k)"),
], "regenerated SITA output (contains chat-template leakage artifact)")

regen("Regen_gd/Logistic_regression_gradient_descent/Trial1.lean", "GD",
      "Logistic regression", "gradient descent", [
    ("definitional", "Logistic_regression_problem.f", "unfaithful",
     "DROPS the data vectors a_i: writes log(1+exp(-b i • x)) instead of "
     "log(1+exp(-b_i a_iᵀ x)); wrong object"),
], "regenerated SITA output (badly malformed; pathological proof)")

regen("Regen_gd/Quadratic_minimization_gradient_descent/Trial1.lean", "GD",
      "Quadratic minimization", "gradient descent", [
    ("definitional", "Quadratic_minimization_problem.f", "unfaithful",
     "encodes 1/2||x - Qx - c||^2, NOT 1/2 xᵀQx + cᵀx — completely different objective"),
    ("instance_soundness", "Quadratic_minimization_GD.Gradient_Descent", "faithful",
     "INSTANCE IS SOUND (no sorry) even though f is definitionally wrong — checks are orthogonal"),
    ("statement_faithfulness", "Quadratic_minimization_GD.gradient_method", "faithful",
     "generic GD O(1/k) bound; faithful as a statement (the fault is upstream in f, check 1)"),
], "regenerated SITA output; teaching case: sound instance + unfaithful def")

# ============================================================ 3) MOCK FIXTURES
def mockf(relpath, fam, pname, cls, targets, provenance):
    p = MOCK / relpath
    text = p.read_text(encoding="utf-8")
    sp = spec(pname, cls)
    for (check, target, truth, note) in targets:
        add(lean_text=text, check=check, target=target, informal=sp,
            source_bucket="mock", path="tests/mock_data/artifacts/" + relpath,
            provenance=provenance, truth=truth, note=note, fam=fam)

mockf("faithful_leastsquares.lean", "GD", "Least squares problem", "gradient descent", [
    ("definitional", "LeastSquares_problem.f", "faithful", "1/2||Ax-b||^2"),
    ("instance_soundness", "LeastSquares_GD.Gradient_Descent", "faithful", "no sorry"),
    ("statement_faithfulness", "LeastSquares_GD.gradient_method", "faithful", "O(1/k)"),
], "hand-built faithful fixture")

mockf("hollow_lasso.lean", "PGD", "Lasso problem", "proximal gradient", [
    ("definitional", "Lasso_pro.f", "unfaithful",
     "uses ||x|| (L2) for the regulariser instead of ||x||_1 (L1) — wrong norm"),
    ("instance_soundness", "Lasso_pg.pg", "unfaithful",
     "HOLLOW: update <- self.bad_update_lemma (undefined/unproven); instance cannot certify"),
    ("statement_faithfulness", "Lasso_convergence", "unfaithful",
     "rate 1/(k t) (missing factor 2 vs 1/(2k t)); whole theorem is `sorry`"),
], "hand-built hollow fixture")

# ============================================================ 4) PLANTED: check-1 def-eq corruptions
# The 'generated def' under test is a candidate RHS for the least-squares objective f(x)=1/2||Ax-b||^2.
DEFEQ_HEADER = (
    "-- A SITA-style formalization of the least-squares objective.\n"
    "-- The class fixes A : Matrix (Fin m) (Fin n) ℝ and b : Fin m → ℝ.\n"
    'local notation "‖" x "‖₂" => @Norm.norm _ (PiLp.instNorm 2 fun _ ↦ ℝ) x\n'
    "class LeastSquares_problem (A : Matrix (Fin m) (Fin n) ℝ) (b : Fin m → ℝ) where\n"
    "  hA : A ≠ 0\n\n"
)
DEFEQ_CASES = [
    ("identical",       "1 / 2 * ‖A *ᵥ x - b‖₂ ^ 2",  "faithful",   "exact match"),
    ("div-form",        "‖A *ᵥ x - b‖₂ ^ 2 / 2",       "faithful",   "(•)/2 = 1/2*(•)"),
    ("inv-form",        "2⁻¹ * ‖A *ᵥ x - b‖₂ ^ 2",     "faithful",   "2⁻¹ = 1/2"),
    ("factored",        "(‖A *ᵥ x - b‖₂ ^ 2) * (1/2)", "faithful",   "commuted 1/2 factor"),
    ("wrong-const-1/3", "1 / 3 * ‖A *ᵥ x - b‖₂ ^ 2",   "unfaithful", "1/3 ≠ 1/2"),
    ("missing-half",    "‖A *ᵥ x - b‖₂ ^ 2",           "unfaithful", "dropped 1/2 factor"),
    ("no-square",       "1 / 2 * ‖A *ᵥ x - b‖₂",       "unfaithful", "missing the square"),
    ("sign-flip",       "1 / 2 * ‖A *ᵥ x + b‖₂ ^ 2",   "unfaithful", "+b instead of -b"),
]
sp_ls = spec("Least squares problem", "gradient descent")
for (label, rhs, truth, note) in DEFEQ_CASES:
    text = DEFEQ_HEADER + (
        "def LeastSquares_problem.f (_ : LeastSquares_problem A b) :\n"
        "    EuclideanSpace ℝ (Fin n) → ℝ :=\n"
        f"  fun x ↦ {rhs}\n")
    add(lean_text=text, check="definitional", target="LeastSquares_problem.f", informal=sp_ls,
        source_bucket="planted", path=f"planted/defeq/{label}", provenance="check1_defeq.py case",
        truth=truth, note=note)

# ============================================================ 5) PLANTED: check-2 sorry-injection
# Take a gold instance source and replace exactly one condition field's RHS with `by sorry`.
SORRY_FAMILIES = [
    ("Example/GD_example.lean", "GD", "Least squares problem", "gradient descent",
     "LeastSquares_GD.Gradient_Descent", ["update", "hl", "step₁", "initial"]),
    ("Example/PGD_example.lean", "PGD", "Lasso problem", "proximal gradient",
     "proximal_gradient_method_Lasso.proximal_gradient_method", ["initial", "update"]),
]
for (relpath, fam, pname, cls, inst, fields) in SORRY_FAMILIES:
    base = (LEAN / relpath).read_text(encoding="utf-8")
    sp = spec(pname, cls)
    for fld in fields:
        patched, n = re.subn(rf"(\n\s*{re.escape(fld)}\s*:=)[^\n]*", r"\1 by sorry", base, count=1)
        if n != 1:
            continue
        add(lean_text=patched, check="instance_soundness", target=inst, informal=sp,
            source_bucket="planted", path=f"planted/sorry/{relpath}::{inst}::{fld}",
            provenance="fault_injection.py sorry-injection", truth="unfaithful",
            note=f"condition field `{fld}` replaced by `by sorry` -> hollow by construction", fam=fam)

# ============================================================ 6) PLANTED: scratch variants
sc = (LEAN / "_scratch/GD_example_hollow.lean").read_text(encoding="utf-8")
add(lean_text=sc, check="instance_soundness", target="LeastSquares_GD.Gradient_Descent",
    informal=spec("Least squares problem", "gradient descent"),
    source_bucket="planted", path="_scratch/GD_example_hollow.lean",
    provenance="scratch planted hollow", truth="unfaithful",
    note="hl field is `by sorry` -> hollow; update_cor still sorry-free", fam="GD")

wr = (LEAN / "_scratch/GD_wrongrate.lean").read_text(encoding="utf-8")
sp_ls = spec("Least squares problem", "gradient descent")
add(lean_text=wr, check="transfer_validity", target="LeastSquares_GD.gradient_method", informal=sp_ls,
    source_bucket="planted", path="_scratch/GD_wrongrate.lean", provenance="scratch planted wrong-rate",
    truth="unfaithful",
    note="claims 1/(3(k+1)t), STRICTLY STRONGER than the abstract 1/(2(k+1)t) the proof apply's "
         "-> not a valid specialization", fam="GD")
add(lean_text=wr, check="statement_faithfulness", target="LeastSquares_GD.gradient_method", informal=sp_ls,
    source_bucket="planted", path="_scratch/GD_wrongrate.lean", provenance="scratch planted wrong-rate",
    truth="unfaithful",
    note="rate constant 3 vs 2: same O(1/k) ORDER but wrong stated bound; borderline — depends on "
         "whether constants count. Flag as a calibration discussion case.", fam="GD")

# ---------------------------------------------------------------- emit
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(20260626)
rng.shuffle(ITEMS)

with (OUT / "items.jsonl").open("w", encoding="utf-8") as f:
    for it in ITEMS:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")
(OUT / "keymap.json").write_text(json.dumps(KEY, ensure_ascii=False, indent=2), encoding="utf-8")

# small provenance/coverage report (private)
from collections import Counter
by_bucket = Counter(v["source_bucket"] for v in KEY.values())
by_check = Counter(v["check"] for v in KEY.values())
by_truth = Counter(v["construction_truth"] for v in KEY.values())
print(f"wrote {len(ITEMS)} items -> {OUT/'items.jsonl'}")
print(f"      keymap          -> {OUT/'keymap.json'}")
print("by source bucket:", dict(by_bucket))
print("by check        :", dict(by_check))
print("by truth        :", dict(by_truth))
