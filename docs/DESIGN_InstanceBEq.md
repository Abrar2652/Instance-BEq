# DESIGN — Instance-BEq Faithfulness Certifier

Technical design for the certifier. Read alongside `SITA_REPO_MAP.md`. This doc specifies the
data contracts and the precise obligation each check discharges, so the implementation can implement
checks independently without re-deriving the math.

---

## 0. Vocabulary

- **Artifact file**: one SITA-generated `.lean` file (a `ProofTrialFinal/*.lean`) realizing one
  instance of one abstract structure.
- **Informal spec**: the JSONL record (`problem_name`, `problem_statement`, `class`, `algorithm`)
  the file was generated from. The ground-truth meaning.
- **Abstract structure (S)**: the `Template/*.lean` the instance is supposed to satisfy
  (classes + abstract theorem). The reusable interface.
- **Certificate**: a record `{def_faithful, instance_sound, transfer_valid, statement_faithful}`
  of booleans + evidence, per artifact.

## 1. Data contracts

### 1.1 Parsed artifact (`artifacts.py` → `ParsedArtifact`)
```python
@dataclass
class Decl:
    kind: Literal["def","class","instance","theorem","lemma","abbrev"]
    name: str
    signature: str          # text between name and := / where
    body: str               # RHS or tactic block or where-block
    span: tuple[int,int]    # (start_line, end_line) in the file
    raw: str                # exact source slice

@dataclass
class ParsedArtifact:
    path: str
    imports: list[str]
    namespaces: list[str]    # open ... and section names
    local_notation: list[str]
    decls: list[Decl]
    # convenience views:
    defs: list[Decl]
    instances: list[Decl]
    theorems: list[Decl]     # theorem+lemma
    informal: dict | None    # the matched JSONL record
    abstract_structure: str | None  # path to the Template file
```
Parser is **text+lightweight-Lean**, not a full Lean frontend: we split on top-level
`def/class/instance/theorem/lemma/abbrev` keywords respecting `where`/`:=`/`by` blocks and
indentation. We do NOT need a full parser because Lean itself is our semantic oracle — the parser
only has to slice declarations accurately enough to (a) name them and (b) hand a focused snippet
to the oracle. Edge cases (nested `let`, multiline signatures, `local notation`) are covered by
mock fixtures `tests/mock_data/parse_*`.

### 1.2 Certificate (`checks` → `CheckResult`)
```python
@dataclass
class CheckResult:
    check: Literal["definitional","instance_soundness","transfer_validity","statement_faithfulness"]
    target: str            # decl name
    passed: bool
    confidence: float | None   # for LLM-assisted sub-checks; None for purely symbolic
    evidence: dict         # tactic that closed it / sorry trace / counterexample / oracle stdout
    cost: dict             # {lean_calls, llm_calls, wall_s}
```

## 2. The Lean oracle (`harness/lean_oracle.py`)

Single responsibility: compile a snippet and report `(ok, errors, warnings, raw)`. Built on
SITA's `interact.compile_file`.

```python
class LeanOracle:
    def __init__(self, lean_cwd, mock=False, mock_db=None): ...
    def check_snippet(self, lean_source: str, imports: list[str]) -> OracleResult
    def check_file(self, path: str) -> OracleResult
    # OracleResult: ok: bool, errors: list[dict], warnings: list[dict], raw: str, uses_sorry: bool
```

Implementation notes:
- We write the snippet to a temp `.lean` under `Code/lean/Optlib/Autoformalization/_scratch/`
  (so imports resolve against the built Optlib), compile, parse, then delete.
- `uses_sorry` is set if any warning matches `declaration uses 'sorry'` OR our SorryDetect
  meta-program flags transitive sorry (see §5).
- **Mock mode** (`mock=True`): instead of invoking Lean, look up the snippet's hash (or a tag we
  embed) in `mock_db` (a dict shipped with the fixtures) and return the canned `OracleResult`.
  This is what keeps the test suite Lean-free and CI-fast. Every fixture declares its expected
  oracle verdict.

## 3. Check 1 — Definitional faithfulness (`checks/definitional.py`)

**Goal:** the generated `def D_gen` faithfully encodes the informal object.

**Obligation.** Produce a *reference* definition `D_ref` of the same object, derived
independently from the informal spec, and discharge:
```
example : D_gen = D_ref := by <tactic-ensemble>
-- or, when not definitionally equal but extensionally so:
example : ∀ x, D_gen x = D_ref x := by ext x; <tactic-ensemble>
```
If the ensemble closes the goal → faithful. If it fails in *both* directions and a
bidirectional `↔`/`=` attempt also fails → unfaithful (or "unknown", see recall caveat).

**Where does `D_ref` come from?** This is the one genuinely open design choice. Three options,
implement (a) first, keep (b)/(c) behind a flag for the ablation:
- (a) **Retrieval-grounded**: pull the canonical Optlib characterization from
  `theorem_database/Optlib/*.json` (e.g., the `prox_prop` def, the `LeastSquares` objective
  pattern) and instantiate its parameters from the informal spec. Highest precision, needs the
  object to exist in the corpus.
- (b) **LLM-generated, independently**: prompt the LLM (via `harness/llm.py`) to formalize *only*
  the objective/operator from the informal spec, with a different prompt and no sight of `D_gen`.
  Then check `D_gen = D_ref`. Independence is the point — a shared bug would have to occur twice.
- (c) **Property-based**: instead of a reference def, assert known *properties* the object must
  satisfy (e.g., the Lasso objective is convex, its value at 0 is ½‖b‖², its prox has the
  soft-threshold closed form) and discharge each. Strongest against "looks right but isn't",
  weakest coverage. Good as a *secondary* signal.

**Tactic ensemble** (try in order, first success wins; record which one):
`rfl` → `simp only [D_gen, D_ref]` → `unfold D_gen D_ref; ring` →
`unfold D_gen D_ref; ext x; ring_nf; simp` → `decide` (for finite) → LLM-suggested tactic
(via `harness/llm.py`, last resort, lowers confidence).

**Output:** `CheckResult(check="definitional", confidence=None if pure-symbolic)`.

## 4. Check 2 — Instance soundness (`checks/instance_soundness.py`)

**Goal:** the bridging `instance I : S ... where ...` genuinely certifies S's conditions, i.e.
no field is satisfied by a `sorry`-tainted proof.

**Method.**
1. Parse the instance's `where` fields (or anonymous-constructor fields). For `GD_example`:
   `x, t, l, update, hl, step₁, initial`.
2. For each field that corresponds to a *condition/proof* obligation of S (not raw data like
   `x`, `t`), resolve the proof term it's assigned (often a named lemma, e.g.
   `update := self.update_cor`, `hl := pro.pos_l`).
3. Run SorryDetect (§5) on each such proof term: does its full dependency closure contain
   `sorryAx`, `admit`, or a non-allowed axiom?
4. **Sound** ⇔ every condition field's proof closure is sorry-free and axiom-clean.

**Why this is the headline check.** SITA *claims* instances "certify that the necessary
structural conditions are satisfied." Step-6 harmless-fixing can leave a field proven by `sorry`.
Such an instance compiles and *looks* like a certificate but certifies nothing. Quantifying how
often this happens across the 42-seed outputs is our motivating statistic.

**Allowed axioms** (`config.py: ALLOWED_AXIOMS`): the Mathlib-standard
`propext, Classical.choice, Quot.sound`. Anything else (especially `sorryAx`) → unsound.

**Output:** `CheckResult(check="instance_soundness", evidence={field: sorry_trace})`.

## 5. SorryDetect (`lean/InstanceBEq/SorryDetect.lean`)

A small Lean meta-program (elaborator command) that, given a declaration name, walks its
`ConstantInfo` value's dependency set via `CollectAxioms` (the mechanism behind `#print axioms`)
and reports whether `sorryAx` (or any disallowed axiom) appears.

```lean
-- pseudocode of the command we expose
open Lean Elab Command in
elab "#faithful_axioms " id:ident : command => do
  let cinfo ← getConstInfo id.getId
  let axset ← collectAxioms id.getId   -- reuse Lean's axiom collector
  -- print a machine-parseable line our Python oracle greps:
  logInfo s!"AXIOMS {id.getId} :: {axset.toList}"
```
Python side: append `#faithful_axioms <decl>` to the snippet, compile, grep the `AXIOMS ...`
line, check membership against `ALLOWED_AXIOMS`. This is more reliable than parsing the
`declaration uses 'sorry'` warning because it catches *transitive* sorry through helper lemmas.

> Implementation note: Lean exposes `Lean.collectAxioms` / `CollectAxioms.collect`. Confirm the
> exact API name for v4.13.0 when wiring this (the lead can verify in a `lake env lean` REPL).
> Mock mode returns canned axiom sets from fixtures.

## 6. Check 3 — Theorem transfer (`checks/theorem_transfer.py`)

Two sub-checks.

### 6a. Transfer validity (symbolic, high precision)
**Goal:** the instance theorem `T_inst` is a genuine specialization of the abstract `T_abs`.
**Method:** synthesize the canonical transfer proof and compile it:
```
example : <T_inst.signature> := by
  apply <T_abs> (alg := <instance-bridge>) <discharge side-conditions from the instance>
```
If it closes → transfer valid. We *generate* this proof from S's interface (we know `T_abs`'s
name and hypothesis list from the Template) and the instance's bridge name. This is exactly the
pattern `GD_example.gradient_method` uses (`apply gradient_method_convergence (alg := ...) ...`).
Mock fixtures include both a valid transfer and a *mis-stated* `T_inst` (wrong rate constant)
where the `apply` fails to close → correctly flagged unfaithful.

### 6b. Statement faithfulness (LLM-assisted + symbolic, BEq+-style)
**Goal:** `T_inst`'s *statement* matches the informal claim (right rate, hypotheses, inequality
direction) — catches the case where transfer is valid but the theorem proves something weaker/
different than what the paper claims.
**Method:**
1. Back-translate `T_inst` to natural language (reuse SITA `backtranslation.py`).
2. Extract the structured claim (LHS, relation, RHS-rate, hypotheses) from both the back-
   translation and the informal spec.
3. Symbolic-compare: when both sides are expressible as Lean props, attempt the BEq+ bidirectional
   proof `T_inst.concl ↔ informal.concl`; when not, fall back to a calibrated LLM-judge over the
   structured claims, with confidence recorded.

This is the one check where LLM assistance is unavoidable (the informal side is natural language).
We therefore (i) record confidence, (ii) report it separately, and (iii) in the paper, headline
the symbolic checks (1, 2, 3a) and treat 3b as the bridge to the informal world with its
calibration curve shown honestly.

## 7. Baselines (must be apples-to-apples)

- **A. type-check-only** (`baselines/typecheck_only.py`): file compiles with zero errors → "good".
  This is the implicit SITA file-level metric. It will pass hollow instances and mis-stated
  theorems — that's the point.
- **B. majority-voting** (`baselines/majority_voting.py`): port SITA's `majorty_voting.py` scoring;
  threshold the MV score to a binary "faithful" call. Compares us against SITA's *own* semantic
  proxy.
- **C. LLM-judge** (`baselines/llm_judge.py`): ReForm-style — show the LLM (informal, formal) and
  ask "faithful? yes/no" with rationale. Strong modern baseline; we expect it to beat A but trail
  our symbolic precision and to be miscalibrated.

All baselines consume the same `ParsedArtifact` + informal spec and emit the same
`CheckResult`-shaped verdict, so `eval/metrics.py` scores them identically.

## 8. Evaluation (`eval/`)

- `run_certifier.py --inputs <folder> --mode {mock,real}`: certify every artifact, dump
  per-artifact certificates + a run-level summary JSON.
- `metrics.py`: against the human-annotated gold (`annotation/`), compute per-check and overall
  **precision, recall, F1**; compute **Kendall τ** between each method's scores and human scores
  (the BEq+ correlation protocol); produce the comparison table and the calibration plot for 3b.
- The motivating statistic ("% of type-checking instances that are hollow/unfaithful") is just
  the certifier's failure rate on the type-check-passing subset.

## 9. Cost model & parallelism

- Symbolic checks dominated by Lean compile latency (~seconds/snippet against built Optlib).
  Embarrassingly parallel over artifacts → Slurm array job, one artifact per task, or a thread
  pool mirroring SITA's `max_workers`.
- LLM calls (reference-def gen for 1b, back-translation for 3b, baseline C) are network-bound;
  cache aggressively keyed on (prompt hash, model, temperature).
- Reuse SITA's `_scratch` compile dir pattern; never compile inside the source tree's tracked
  files.

## 10. Open design questions to resolve with the lead (surface, don't silently decide)

1. Reference-def source for check 1: retrieval (a) vs independent-LLM (b) vs property-based (c)
   as the *primary*. Recommendation: (a) primary, (b) ablation, (c) secondary signal.
2. How to bound check-1 recall loss: report "unknown" as a third verdict vs forcing binary.
   Recommendation: three-way {faithful, unfaithful, unknown}; in headline numbers, treat
   unknown conservatively and report coverage.
3. Whether 3b's LLM-judge fallback is allowed into the "formal certificate" or kept as a clearly
   separate "informal-bridge" score. Recommendation: keep separate; the formal certificate is
   1 ∧ 2 ∧ 3a only.
