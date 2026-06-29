# Adjudication Report — Faithfulness Gold Benchmark

**Adjudicator pass over the 57-item blind pool** (`instance_beq/annotation/pool/`), producing
`instance_beq/annotation/gold.jsonl`. Five expert raters (A1–A5) each labelled all 57 items blind;
the adjudicator was non-blind (answer key, rater reasons, and real Lean sources all read).

Date: 2026-06-26.

---

## (a) Trivial-unanimous vs adjudicated

| Bucket | Count |
|---|---|
| Items adjudicated (overrode majority/key, or resolved a split) | **5** |
| Trivial-unanimous, gold = unanimous label = construction_truth | **52** |
| **Total** | **57** |

- 53 items were unanimous (5-0) in the panel. Of those, 52 are trivial-unanimous (gold taken
  directly). The one remaining unanimous item — **IT0036** — is adjudicated because the unanimous
  panel verdict (`unfaithful`) **disagrees with construction_truth** (`faithful`); the panel was
  right and the key was wrong (correction below).
- 4 items were split (IT0040, IT0043, IT0048, IT0057); all 4 are adjudicated.

The five adjudicated items: **IT0036, IT0040, IT0043, IT0048, IT0057**.

---

## (b) Contested items — votes, decision, deciding argument

### IT0036 — `instance_soundness`, `LeastSquares_GD.Gradient_Descent`, `tests/mock_data/artifacts/faithful_leastsquares.lean`
- **Votes:** unfaithful 5 / faithful 0 (unanimous). **construction_truth:** faithful (suspected wrong).
- **Gold:** `unfaithful` (adjudicated; overrides the key, **keymap correction**).
- **Deciding argument (integrity gate, traced from the real fixture):** the instance is
  ```lean
  instance LeastSquares_GD.Gradient_Descent (self : LeastSquares_GD pro x₀) : ... where
    ...
    update := self.update_cor
    hl := pro.pos_l
    step₁ := self.ht
    initial := self.initial
  ```
  but the fixture (full 28-line file) does **not** define the `LeastSquares_GD` class, the
  `update_cor` lemma, the `pos_l` lemma, the `unconstrained_problem` instance, or the
  `diff/smooth/convex` lemmas. So `self.update_cor` and `pro.pos_l` reference helpers that are
  **absent**; the certifying proofs cannot be exhibited and the file would not compile standalone.
  An instance whose condition fields are discharged by undefined/unprovable helpers is **not
  certified-sound** — it is hollow-by-omission, the same failure class as a `sorry`-backed field.
  Per protocol §"Quality checks" and the study integrity gate, a non-certifiable/abstained
  soundness case must **not** be scored faithful. All five raters reached this independently
  (A1/A2 conf 4/—, A2/A4/A5 flagged uncertain). The key's note "no sorry" is literally true but
  irrelevant: absence of a textual `sorry` does not equal presence of a real proof. The final
  confirmation step on the built toolchain is `#print axioms LeastSquares_GD.Gradient_Descent`
  (expected: error / unresolved reference, i.e. uncertifiable), which we cannot run here (no
  Mathlib build); the textual trace is decisive on its own.
- **Note vs the real `Example/GD_example.lean`:** the *real* GD example (IT0002) is genuinely
  sound — there `update_cor`, `pos_l`, the class, and the `unconstrained_problem` instance are all
  defined and sorry-free (verified: 0 sorry in the file). IT0036's fixture is a *trimmed* copy that
  kept the instance but dropped its scaffolding, which is exactly why it is non-certifiable.

### IT0040 — `statement_faithfulness`, `Lasso_convergence`, `tests/mock_data/artifacts/hollow_lasso.lean`
- **Votes:** unfaithful 3 (A1,A4,A5) / faithful 2 (A2,A3). **construction_truth:** unfaithful.
- **Gold:** `unfaithful` (adjudicated; split resolved). A1/A4/A5 right.
- **Deciding argument (traced from the real fixture):**
  ```lean
  theorem Lasso_convergence (xm) :
    ∀ k : ℕ, pro.target (alg.x k) - pro.target xm ≤ 1 / (k * alg.t) * ‖x0 - xm‖ ^ 2 := by sorry
  ```
  vs abstract `proximal_gradient_converge`, which gives `∀ k : ℕ+, … ≤ 1/(2*k*alg.t)*‖x₀-xm‖²`.
  Two faults compound: (i) the leading constant drops the factor 2 (`1/(k t)` vs `1/(2 k t)`), and
  (ii) the quantifier is widened from `ℕ+` to `ℕ`. The quantifier widening is the decisive one:
  at `k = 0`, `1/(0 * t) = 1/0 = 0` in Lean, so the statement asserts
  `target(x⁰) − target(xm) ≤ 0`, i.e. the very first iterate is already optimal — **false** in
  general. A2/A3 voted faithful on a "looser-but-still-true bound" rule, but that rule does not
  apply: the bound is not merely loose, it is *false* at k=0 (and the constant is *tighter*, not
  looser, for k≥1). The whole theorem body is also `sorry`, so nothing is actually proven. Either
  fault alone is disqualifying; together they make `unfaithful` unambiguous. (A4 and A5 explicitly
  named the k=0 falsity.)

### IT0043 — `definitional`, `LeastSquares_problem.f`, `planted/defeq/inv-form`
- **Votes:** faithful 4 (A1,A2,A4,A5) / unfaithful 1 (A3). **construction_truth:** faithful.
- **Gold:** `faithful` (adjudicated; split resolved). A1/A2/A4/A5 right; A3 wrong.
- **Deciding argument:** source is `f := fun x ↦ 2⁻¹ * ‖A *ᵥ x - b‖₂ ^ 2`. This is `−b` inside the
  norm and `2⁻¹ = 1/2`, so it is definitionally `½‖Ax−b‖²` — exactly the informal object. A3
  labelled it `unfaithful` claiming "wrong sign inside norm: ½‖Ax + b‖²", which is a **misread**:
  the source plainly has `- b`. A3 swapped its reading of IT0043 (the `2⁻¹` inv-form, faithful) and
  IT0048 (the `+ b` sign-flip, unfaithful) — see IT0048. This is an annotation error, not a genuine
  judgment call.

### IT0048 — `definitional`, `LeastSquares_problem.f`, `planted/defeq/sign-flip`
- **Votes:** unfaithful 4 (A1,A2,A4,A5) / faithful 1 (A3). **construction_truth:** unfaithful.
- **Gold:** `unfaithful` (adjudicated; split resolved). A1/A2/A4/A5 right; A3 wrong.
- **Deciding argument:** source is `f := fun x ↦ 1 / 2 * ‖A *ᵥ x + b‖₂ ^ 2` — `+ b` instead of
  `− b`. This encodes ½‖Ax + b‖², a different objective (the residual sign is flipped), so it is
  definitionally unfaithful to ½‖Ax − b‖². A3 labelled it `faithful` ("matches ½‖Ax-b‖²"), again a
  misread — the source has `+ b`. IT0043 and IT0048 are A3's mirror-image errors: A3 read the
  `2⁻¹` item as a sign-flip and the sign-flip item as fine. Both decided against A3.

### IT0057 — `statement_faithfulness`, `LeastSquares_GD.gradient_method`, `_scratch/GD_wrongrate.lean`
- **Votes:** unfaithful 4 (A1,A2,A4,A5) / faithful 1 (A3). **construction_truth:** unfaithful.
- **Gold:** `unfaithful`, **`uncertain = true`** (adjudicated; split resolved). A1/A2/A4/A5 right;
  A3 wrong.
- **Deciding argument (traced from the real file):** the stated bound is
  `… ≤ 1 / (3 * (k + 1) * alg.t) * ‖x₀ - xm‖ ^ 2`, while the abstract
  `gradient_method_convergence` (and the standard GD result) gives `1 / (2 * (k + 1) * alg.t)`.
  Same `O(1/k)` *order*, but the stated constant (3) makes the RHS **strictly smaller** than what GD
  actually guarantees — a *tighter, false* bound (an over-claim), not a looser-but-true one. For
  `statement_faithfulness`, the protocol counts "wrong convergence rate" as a mattering discrepancy;
  a wrong leading constant that turns a true bound into a false one qualifies. So gold = unfaithful.
  We set `uncertain = true` because this is the canonical *constants-vs-order* calibration case the
  key itself flags: an annotator who scopes "rate" to mean only asymptotic order (ignoring
  constants) could defensibly call it faithful — that is precisely the human-judgment boundary this
  benchmark is meant to probe. A3 took the order-only view (faithful); the deciding panel and the
  key take the constant-matters view. Note the *sibling transfer_validity item* **IT0056** (same
  file, same `3` constant) is unanimous `unfaithful` and **not** borderline: there the wrong
  constant makes the `apply` of the abstract lemma fail outright (you cannot derive a strictly
  tighter bound from a weaker one), so transfer validity is decidably false regardless of how one
  scopes "rate". IT0057 vs IT0056 is a clean illustration that the *constant* sinks transfer
  validity hard but is a judgment call for statement faithfulness.

---

## (c) Instance-soundness integrity-gate table (decidable cross-check)

For every `instance_soundness` item, the deciding field(s) were traced in the real source file
(keymap path). "Sound" = zero `sorry`/`admit`/undefined-helper condition fields; "Hollow" = at
least one condition field discharged by `sorry`/`admit` or an absent/unprovable helper. Raw data
fields (`x`, `t`) carry no proof obligation and are exempt. Built-toolchain confirmation is
`#print axioms <target>` (not runnable here; textual trace given). All 5 raters agreed on every
soundness item (κ = 1.0 on this check), and the gold matches the axiom-tracer conclusion on all 19.

| id | target | source file | deciding field(s) | verdict |
|---|---|---|---|---|
| IT0002 | `LeastSquares_GD.Gradient_Descent` | `Example/GD_example.lean` | update←update_cor, hl←pos_l, step₁←ht, initial (all real; file 0 sorry) | **Sound** |
| IT0008 | `proximal_gradient_method_Lasso.proximal_gradient_method` | `Example/PGD_example.lean` | update←update_cor (real, via norm_one_proximal); initial (file 0 sorry) | **Sound** |
| IT0013 | `Lasso.isProblem` | `Example/ADMM_example.lean` | empty `where` (data-only Problem; no proof-obligation fields). File's 10 sorries are in *other* lemmas | **Sound** |
| IT0014 | `Lasso_ADMM.toADMM` | `Example/ADMM_example.lean` | hX/hY←uniq_subX/uniq_subY (sorry), iter₁/₂/₃←iter_cor1/2/3 (sorry) | **Hollow** |
| IT0015 | `isConvexKKT.isLasso_KKT` | `Example/ADMM_example.lean` | subgrad₁/subgrad₂/eq←isLasso_KKT₁/₂/₃ (all sorry) | **Hollow** |
| IT0022 | `JointSparseCoding_problem.ProblemData` | `Example/BCD_example.lean` | conH/lpos/lip←sorry helpers (lbdf/lbdg/hf/hg are real) | **Hollow** |
| IT0023 | `BCD_JointSparse.BCD` | `Example/BCD_example.lean` | s₁/s₂←update_cor1/update_cor2 (sorry) | **Hollow** |
| IT0026 | `LeastSquares_GD.Gradient_Descent` | `Regen_gd/Least_squares_problem_gradient_descent/Trial1.lean` | update_cor/pos_l/ht/initial (all real; file 0 sorry) | **Sound** |
| IT0029 | `Ridge_regression_GD.Gradient_Descent` | `Regen_gd/Ridge_regression_gradient_descent/Trial1.lean` | update_cor/pos_l/ht/initial (all real; instance 0 sorry — chat-leak noise is outside the fields) | **Sound** |
| IT0033 | `Quadratic_minimization_GD.Gradient_Descent` | `Regen_gd/Quadratic_minimization_gradient_descent/Trial1.lean` | update_cor/pos_l(via Transpose_mul_self_eq_pos_definite)/ht/initial (all real; 0 sorry). Wrong f is a *definitional* fault (IT0032), orthogonal to soundness | **Sound** |
| IT0036 | `LeastSquares_GD.Gradient_Descent` | `tests/mock_data/artifacts/faithful_leastsquares.lean` | update←self.update_cor, hl←pro.pos_l reference helpers + the LeastSquares_GD class **absent from the fixture** → non-certifiable | **Hollow** |
| IT0039 | `Lasso_pg.pg` | `tests/mock_data/artifacts/hollow_lasso.lean` | update←self.bad_update_lemma (undefined helper; class/composite_pro also absent) | **Hollow** |
| IT0049 | `LeastSquares_GD.Gradient_Descent` | `planted/sorry/...::update` | update := by sorry | **Hollow** |
| IT0050 | `LeastSquares_GD.Gradient_Descent` | `planted/sorry/...::hl` | hl := by sorry | **Hollow** |
| IT0051 | `LeastSquares_GD.Gradient_Descent` | `planted/sorry/...::step₁` | step₁ := by sorry | **Hollow** |
| IT0052 | `LeastSquares_GD.Gradient_Descent` | `planted/sorry/...::initial` | initial := by sorry | **Hollow** |
| IT0053 | `proximal_gradient_method_Lasso.proximal_gradient_method` | `planted/sorry/...::initial` | initial := by sorry | **Hollow** |
| IT0054 | `proximal_gradient_method_Lasso.proximal_gradient_method` | `planted/sorry/...::update` | update := by sorry | **Hollow** |
| IT0055 | `LeastSquares_GD.Gradient_Descent` | `_scratch/GD_example_hollow.lean` | hl := by sorry (update_cor still sorry-free, but one tainted condition field suffices) | **Hollow** |

**Soundness tally:** **6 Sound** (IT0002, IT0008, IT0013, IT0026, IT0029, IT0033) and
**13 Hollow** (IT0014, IT0015, IT0022, IT0023, IT0036, IT0039, IT0049–IT0055), 19 soundness items
total.
Every soundness gold label equals the axiom-tracer conclusion, satisfying the decidable
cross-check (protocol §"Quality checks": human label and tool must agree).

---

## (d) Corrections to `keymap.json`'s construction_truth

| id | original truth | corrected truth | why |
|---|---|---|---|
| **IT0036** | faithful | **unfaithful** | The mock fixture `faithful_leastsquares.lean` keeps the `LeastSquares_GD.Gradient_Descent` instance but drops its supporting scaffolding: the `LeastSquares_GD` class, the `update_cor` and `pos_l` lemmas, and the `unconstrained_problem` instance are all absent from the artifact. The instance's condition fields therefore reference undefined helpers; the certifying proofs cannot be exhibited and the file would not compile standalone. By the soundness criterion (a condition field discharged by a `sorry`/`admit`/undefined helper makes the instance hollow) and by protocol (a non-certifiable/abstained soundness case must not be scored faithful), the correct label is `unfaithful`. The key's note "no sorry" is true but not sufficient: absence of a textual `sorry` ≠ presence of a real proof. Confirmed independently by all 5 raters. |

The correction was applied in-place: `keymap.json` IT0036 now has `construction_truth: "unfaithful"`,
retains the original under `construction_truth_original: "faithful"`, and the `note` records the
reasoning and date. No other construction_truth values were changed; the other 56 items' keys were
all confirmed correct against the panel and (for soundness/definitional items) the real sources.

---

## (e) Final gold class balance and uncertainty

| Metric | Value |
|---|---|
| **faithful** | 34 |
| **unfaithful** | 23 |
| **Total** | 57 |
| **uncertain = true** | 1 (IT0057) |
| **adjudicated = true** | 5 (IT0036, IT0040, IT0043, IT0048, IT0057) |

By check:
- `definitional`: 24 items. Faithful 17, unfaithful 7 (IT0031, IT0032, IT0038, IT0045, IT0046,
  IT0047, IT0048).
- `instance_soundness`: 19 items. Sound/faithful 6, hollow/unfaithful 13.
- `statement_faithfulness`: 10 items (IT0003/09/16/24/27/30/34/37/40/57). Faithful 8,
  unfaithful 2 (IT0040, IT0057).
- `transfer_validity`: 4 items (IT0004/10/17/56). Faithful 3, unfaithful 1 (IT0056).

**Calibration takeaways for the human study:**
- A3 is the weak rater (overall κ-vs-truth 0.912; the only rater wrong on a *definitional* item):
  A3 swapped the readings of IT0043 (`2⁻¹`, faithful) and IT0048 (`+b` sign-flip, unfaithful), and
  took the order-only view on IT0057. None of A3's three misses is a defensible judgment call except
  IT0057; the 43/48 swap is a transcription/attention error worth flagging in rater training.
- The hardest *genuine* boundary is the **constant-vs-order** question (IT0057, and the looser-bound
  trap in IT0040). statement_faithfulness has the lowest panel agreement (Fleiss 0.585), consistent
  with this being the non-decidable check where human judgment matters most. The gold takes the
  position: **a wrong leading constant that makes the stated bound false (IT0057 over-claim) or that
  rests on a falsified quantifier (IT0040 k=0) is unfaithful**, even when the asymptotic order is
  right. IT0057 is the single item carrying `uncertain = true` to mark it as the calibration
  discussion case.
- instance_soundness and transfer_validity are decidable and had perfect panel agreement (κ = 1.0);
  the human labels there validate the tool's plumbing rather than exercise judgment. The one
  soundness subtlety the panel handled correctly is the *non-certifiable* variant (IT0036, IT0039):
  an instance is hollow not only when a field is literally `by sorry` but also when its field
  references a helper/class that is undefined or unprovable in the artifact.

---

### Deliverables
- `instance_beq/annotation/gold.jsonl` — 57 gold rows (protocol format + audit fields).
- `instance_beq/annotation/ADJUDICATION_REPORT.md` — this report.
- `instance_beq/annotation/pool/keymap.json` — IT0036 construction_truth corrected (original
  preserved).
