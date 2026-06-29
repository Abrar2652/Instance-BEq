# Human-Correlation Study — Step-by-Step Runbook

> **Audience:** the project lead (and any co-annotator), executing the study manually.
> **Goal:** produce expert faithfulness labels and use them to (a) score Instance-BEq and the
> baselines with **precision / recall / F1**, and (b) show Instance-BEq's scores **correlate with
> human judgment (Kendall τ)** better than the LLM-judge baseline.
> This expands `instance_beq/annotation/protocol.md` into an actionable checklist. Read that file
> for the label *criteria*; read this file for *how to run the whole study end-to-end*.

---

## 0. Why this study exists (what each reviewer objection it answers)

| Reviewer objection | This study's answer |
|---|---|
| "Your metric is arbitrary / doesn't reflect real faithfulness." | Kendall τ vs. expert labels, the BEq+ protocol. |
| "It's just an LLM judging itself." | We show the **symbolic** certifier beats the **LLM-judge** on precision AND τ. |
| "Benchmark too small." | ≥300–500 artifact-component labels, larger than BEq's 200 statement pairs. |
| "Labels are noisy / subjective." | Two independent annotators, Cohen's κ per check, adjudication. |
| "Soundness check is trivial." | True for check 2 (decidable) — we say so; the human-judgment value is concentrated in checks 1 (definitional) and 3b (statement), which are **not** decidable. |

**Key conceptual point to keep straight:** for **instance-soundness (check 2)** the tool is
*decidable and exact*, so the human label is only a plumbing cross-check (human and tool must agree;
a mismatch is an annotation error, not a tool error). The scientifically interesting correlation is
for **definitional (check 1)** and **statement-faithfulness (check 3b)**, where judgment is required.

---

## 1. Roles and prerequisites

- **2 annotators** (A1, A2). Each must be able to: read Lean 4 well enough to see what a `def`/
  `instance`/`theorem` says, and know first-order optimization (gradient descent, proximal
  gradient, ADMM, BCD, Nesterov; convergence rates O(1/k), O(1/k²); convexity, L-smoothness).
  The project lead qualifies; the second can be a labmate given a 30-min calibration (Step 4).
- **1 adjudicator** (can be A1) to resolve disagreements.
- **Tools:** a spreadsheet (Google Sheets / LibreOffice) OR the JSONL workflow in Step 6; the built
  Lean toolchain (for the decidable cross-check); the informal specs
  (`Code/data/problem/problem_test.jsonl`).

---

## 2. Build the item pool (what gets labelled)

Each **item** = one `(file, check, target)` triple. Assemble ~300–500 items from four sources so the
pool spans faithful *and* unfaithful, easy *and* hard:

1. **Gold examples (sound anchors).** The 6 released `Example/*.lean`. Their `def`/`instance`/
   `theorem` targets — mostly faithful, except the known-hollow ADMM/BCD instances. ~40 items.
2. **Planted faults (known-unfaithful anchors).** The fault-injection variants
   (`scripts/fault_injection.py`) and definitional corruptions (`scripts/check1_defeq.py`): each has
   ground truth by construction. ~30 items. *These calibrate the annotators* (their labels must match
   the construction) and seed the unfaithful class.
3. **Regenerated SITA outputs (the realistic bulk).** Run the pipeline (`scripts/run_regen.sh`) over
   all 5 families; take every `def`/`instance`/`theorem` in the final `ProofTrialFinal/*.lean` (and
   the not-fully-correct files too — those are where unfaithfulness lives). This is the bulk and the
   most representative. ~250–400 items. *Use the strongest available generator* (DeepSeek key, or
   `gpt-oss-20b`) so the pool isn't dominated by trivial near-copies (see the GD-pilot lesson:
   weak-model outputs that fail to compile are excluded from the type-check-passing analysis but can
   still be labelled for the definitional/statement checks).
4. **External substrate (optional, strengthens generality).** AMBER's optimization slice
   (arXiv:2602.01291) separates def(construction) from theorem(verify) — a natural out-of-distribution
   set. Add ~30 items if time permits.

**Balance target:** aim for at least ~30% unfaithful items overall (sources 2–3 supply them); a pool
that is 95% faithful makes recall estimates noisy. Do **not** tell annotators which source an item
came from (blind them to the planted/gold provenance to avoid bias — Step 6 shuffles).

**Contamination tag (per item):** record whether the source problem could predate the base model's
training cutoff. Prefer post-cutoff items for the headline τ (the RLM25 strategy). See protocol.md §
"Contamination hygiene".

---

## 3. The label schema (per item)

Annotators fill these fields (criteria in `protocol.md` §"Label set"):

| Field | Values | Notes |
|---|---|---|
| `label` | `faithful` \| `unfaithful` | the core judgment |
| `confidence` | 1–5 | 5 = certain; used for the calibration/ECE analysis of check 3b |
| `uncertain` | true/false | flags items for adjudication regardless of label |
| `reason` | free text, one line | MUST name the specific discrepancy if `unfaithful` |
| `time_sec` | integer | for the effort report; target 3–5 min/item |

Time-box: **3–5 min per target.** If a transfer/statement item is too dense to judge by eye,
consult the Template's abstract theorem for the expected shape, then decide or mark `uncertain`.

---

## 4. Calibration round (do BEFORE the real labelling — 30–45 min)

1. Both annotators independently label the **same** 30 planted/gold items from sources 1–2 (known
   ground truth), blind to which is which.
2. Compute, per check: agreement with ground truth, and A1-vs-A2 agreement.
3. **Gate:** if either annotator's agreement-with-truth on the *definitional* or *statement* checks
   is < 0.8, walk through the misses together, refine the shared understanding of the criteria, and
   repeat with a fresh 15 items. Do not start the real pool until the gate passes.
4. For the *soundness* check, any human≠tool disagreement is resolved in favour of the tool (it is
   decidable); use these to teach annotators what "hollow" means operationally.

---

## 5. Main labelling pass

1. Each item is labelled **independently** by A1 and A2 (no discussion, no seeing each other's
   labels). Keep the two label sets in separate files.
2. Work in blocks of ~50 items with breaks; fatigue degrades label quality.
3. After all items: compute **Cohen's κ per check** (Step 7). Any check with κ < 0.6 → revisit the
   criteria for that check, re-label a sample, and report the final κ honestly.
4. **Adjudication:** the adjudicator resolves every disagreement (and every `uncertain=true`) in a
   joint pass. The adjudicated label is **gold**. Record who adjudicated and the final reason.

---

## 6. Tooling / file format

Gold file = `instance_beq/annotation/gold.jsonl`, one JSON per line (see `gold.example.jsonl`):

```json
{"path":"ProofTrialFinal/Lasso_3.lean","check":"instance_soundness","target":"Lasso_pg.pg",
 "annotator":"A1","label":"unfaithful","confidence":5,"uncertain":false,
 "reason":"field `update_cor` proven via a lemma ending in sorry","provenance":"regen; post-cutoff:no"}
```

Suggested mechanics (pick one):
- **Spreadsheet:** one row per (item × annotator); columns = the schema fields. Export to JSONL at
  the end. Easiest for non-programmer co-annotators.
- **Item-extraction script (recommended):** write `scripts/build_annotation_pool.py` that walks the
  artifact dirs, parses each file's `def`/`instance`/`theorem` targets (reuse `instance_beq/
  artifacts.py` + the `INSTANCE_RE` in `scripts/certify_regen.py`), joins the matching informal spec
  from `problem_test.jsonl`, **shuffles**, and emits one pre-filled row per item with the Lean
  snippet + informal text inline so the annotator only adds `label/confidence/reason`. (Not yet
  built — ~1–2h; ask the implementation to generate it.)

The certifier/baseline predictions to compare against live in `eval_logs/*_result.json` and are
produced by `scripts/certify_regen.py` (Instance-BEq) and `instance_beq/baselines/` (A/B/C).

---

## 7. Analysis (the numbers that go in the paper)

Let HOLLOW/UNFAITHFUL be the **positive** class. For **each method** ∈ {type-check-only (A),
majority-vote (B), LLM-judge (C), **Instance-BEq**} and **each check** ∈ {definitional,
instance-soundness, transfer, statement}:

1. **Precision / Recall / F1** against the adjudicated gold (`instance_beq/eval/metrics.py`).
2. **Kendall τ** between each method's per-item score and the human label (encode faithful=1,
   unfaithful=0; for graded methods use their score). Report τ with a p-value. This is the headline
   correlation; target: Instance-BEq τ and precision **>** LLM-judge (mirrors BEq's 70.6%→100%
   precision jump and BEq+'s τ≈0.872).
3. **Inter-annotator κ** per check (report in the appendix; it bounds the achievable τ).
4. **Calibration of check 3b** (the LLM-assisted one): reliability diagram + **ECE** using the
   model's confidence vs. correctness; show the effect of a confidence threshold on P/R (the
   abstention/coverage trade-off). Checks 1/2/3a are symbolic → no calibration curve (they're exact
   or kernel-sound).
5. **Coverage / abstention:** report the fraction of `unknown` verdicts per check (symbolic checks
   trade recall for precision; never hide abstentions — count a truly-unfaithful abstention as a
   recall miss, no recall inflation).

**Decidable cross-check (integrity gate):** for every `instance_soundness` item, the human gold and
the `#print axioms` tool MUST agree. Any mismatch is an annotation error to fix (the tool is ground
truth there). Spot-audit 10% of `faithful` labels across all checks for hidden `sorry`.

---

## 8. Sample-size & effort estimate

- **Items:** 300–500. At 3–5 min/item × 2 annotators = **30–80 person-hours** total. Budget ~1
  focused week for two people, or spread over 2–3 weeks.
- **Minimum viable** (if time-constrained): 200 items concentrated on the definitional + statement
  checks (where judgment matters), 2 annotators, full κ + τ. This still exceeds BEq's 200 pairs and
  is defensible.

---

## 9. Pitfalls (and how to avoid them)

1. **Provenance leakage** → annotators recognise planted faults. *Fix:* shuffle; strip source tags
   from what the annotator sees.
2. **Class imbalance** → 95% faithful makes recall noisy. *Fix:* ensure ≥30% unfaithful via planted
   + regenerated-failure items.
3. **Labelling soundness by eye** → humans miss transitive `sorry`. *Fix:* for check 2, the tool is
   gold; humans only sanity-check. Concentrate human effort on checks 1 & 3b.
4. **Over-claiming on a tiny unfaithful set** → wide CIs. *Fix:* report confidence intervals
   (bootstrap) on P/R/τ; state n per cell.
5. **Contamination** → model has seen the textbook problem. *Fix:* tag provenance, prefer post-cutoff
   items for the headline τ, report both.
6. **One annotator** → no κ, reviewers discount it. *Fix:* always two independent annotators + κ.

---

## 10. Deliverables checklist

- [ ] `gold.jsonl` with ≥300 adjudicated items (+ both annotators' raw labels retained).
- [ ] Cohen's κ per check (table).
- [ ] P/R/F1 per method × check (the main results table; extends `tab:faults`).
- [ ] Kendall τ per method vs. human (Instance-BEq > LLM-judge) with p-values.
- [ ] Calibration plot + ECE for check 3b.
- [ ] Coverage/abstention rates; contamination breakdown.
- [ ] The integrity-gate result (human vs. decidable tool agreement on soundness = 100% after fixes).
