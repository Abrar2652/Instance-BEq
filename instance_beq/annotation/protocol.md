# Annotation Protocol — Faithfulness Gold Benchmark

Goal: produce ~300–500 human faithfulness labels at the artifact-component level, to (a) score
Instance-BEq and the baselines (precision/recall/F1) and (b) compute Kendall τ with human judgment.

## Unit of annotation

One label per (artifact file, check, target):
- `definitional` → target = a `def` name
- `instance_soundness` → target = an `instance` name
- `transfer_validity` → target = a `theorem`/`lemma` name (is it a valid specialization?)
- `statement_faithfulness` → target = a `theorem`/`lemma` name (does the statement match the claim?)
- `overall` → target = the file (faithful iff all components faithful)

## Label set

`faithful` | `unfaithful`. Use `unfaithful` when:
- **definitional**: the `def` encodes a different object than the informal one (wrong norm,
  missing/extra term, wrong sign, wrong regularization weight, wrong domain/type).
- **instance_soundness**: any *condition* field is discharged by `sorry`/`admit` or a helper that
  is. (Raw data fields like `x`, `t` are exempt — they carry no proof obligation.)
- **transfer_validity**: the instance theorem cannot be obtained by specializing the abstract
  theorem (e.g. it asserts a stronger/unrelated bound the abstract result doesn't give).
- **statement_faithfulness**: the theorem statement differs from the informal claim in a way that
  matters — wrong convergence rate (O(1/k) vs O(1/k²)), wrong inequality direction, dropped/added
  hypothesis, wrong quantity bounded.

When genuinely unsure after the time box below, mark `unfaithful` only if you can name the specific
discrepancy; otherwise discuss (do not guess). Track an `uncertain` flag separately for adjudication.

## Procedure

1. Read the informal spec (the JSONL record: statement + algorithm) first, *before* the Lean.
2. For each target, decide the label using the criteria above. Record a one-line `reason`.
3. Time box: ~3–5 min per target. If the Lean is too dense to judge by eye for
   transfer/statement checks, consult the Template's abstract theorem for the expected shape.
4. Two annotators label each item independently. Compute Cohen's κ. Adjudicate disagreements in a
   joint pass; the adjudicated label is gold.

## Contamination hygiene

Tag each source problem with provenance (textbook/paper + whether it could predate the base
model's training cutoff). Prefer instances authored/committed after the cutoff for the
correlation study (the RLM25 strategy). Record the tag in the gold row.

## Gold file format (`gold.jsonl`, one JSON per line)

```json
{"path": "ProofTrialFinal/Lasso_3.lean",
 "check": "instance_soundness",
 "target": "Lasso_pg.pg",
 "label": "unfaithful",
 "reason": "field `update_cor` proven via a lemma that ends in sorry",
 "uncertain": false,
 "provenance": "Boyd&Vandenberghe; post-cutoff: no"}
```

## Quality checks

- Report inter-annotator κ per check; flag any check with κ < 0.6 for criteria refinement.
- Spot-audit 10% of `faithful` labels for hidden `sorry` (run `#faithful_axioms` as ground truth
  for the soundness check — it is decidable, so the human label and the tool must agree; any
  mismatch is an annotation error to fix, NOT a tool error).
- Keep the soundness check honest: because instance-soundness is *decidable* by the axiom tool,
  human labels there mainly validate the tool's plumbing; the human-judgment value is highest for
  definitional and statement faithfulness, which are not fully decidable.
