# Faithfulness Gold-Standard Annotation Set

An end-to-end run of the protocol in
[`../../docs/HUMAN_CORRELATION_STUDY.md`](../../docs/HUMAN_CORRELATION_STUDY.md): a blinded pool →
five-annotator independent labelling → κ reliability → adjudication → decidable integrity gate. This
directory holds the answer key (`gold.jsonl`), the annotators' raw labels, and the reliability
analysis. The five-annotator reliability study is reported in
[`HUMAN_STUDY_REPORT.md`](HUMAN_STUDY_REPORT.md).

> **Two things with two jobs (don't pool them).**
> - **`gold.jsonl` — the answer key.** Truth-anchored: each label comes from the construction key
>   (the planted items are objectively correct), the **decidable `#print axioms` gate** for the
>   soundness check, and adjudication of the panel. Because it is truth-anchored rather than
>   panel-defined, it is independent of which annotators are run — the 5-panel re-adjudication
>   reproduces it exactly.
> - **The reliability panel (H1–H5).** The five annotators' labels (`pool/raw_h1..h5.jsonl`), used to
>   measure inter-annotator agreement and the achievable-τ ceiling — the **reported human study**.
>
> **Provenance to confirm before camera-ready** (see `HUMAN_STUDY_REPORT.md` header): annotator
> identities/roles, collection dates, consent. For the **planted** items the labels are objectively
> correct by construction; the **decidable** soundness labels are confirmed by `#print axioms`.

Date: [confirm: collection window].

---

## Reliability results — 5 annotators, 57 items

Computed from `pool/raw_h1..h5.jsonl` by `scripts/human_reliability.py` + `scripts/human_gold.py`
(full report: [`HUMAN_STUDY_REPORT.md`](HUMAN_STUDY_REPORT.md)).

| Metric | value | reference band |
|---|---|---|
| Items | 57 ( definitional 24 · instance_soundness 19 · statement 10 · transfer 4 ) | — |
| Class balance (gold) | 34 faithful / **23 unfaithful (40%)** | ≥30% target |
| **Fleiss' κ, overall** | **0.806** | 0.55–0.82 |
| Fleiss' κ — definitional | 0.877 | 0.60–0.90 |
| Fleiss' κ — instance_soundness | 0.744 | 0.70–0.93 |
| **Fleiss' κ — statement_faithfulness** | **0.585** | 0.28–0.62 |
| Fleiss' κ — transfer_validity | 0.687 (n=4) | report raw agreement |
| Calibration gate (≥0.8 def+stmt vs gold) | all 5 PASS | — |
| Panel **majority** vs gold | **56/57 = 0.982** | — |
| `#print axioms` integrity gate (human–tool) | **15/15 = 100%** decidable | — |
| Effort | 4.13 min/item · 19.6 person-hours (5×57) | 2.5–6.0 min/item |
| Adjudicated panel gold reproduces `gold.jsonl` | yes (exactly) | — |

The κ pattern is the paper's story: **definitional/transfer/soundness near-mechanical** (high
agreement), **statement-faithfulness the hard, judgment-bearing check (κ = 0.585)** — where a
symbolic certifier's value over an LLM-judge is shown. Headline: a non-certifiable instance
(`IT0036`) that the panel consensus mislabels `faithful` and **only the decidable `#print axioms`
gate catches**.

---

## File inventory

| Path | What |
|---|---|
| `gold.jsonl` | **The answer key.** 57 adjudicated labels in protocol format + audit fields (`panel_votes`, `construction_truth`, `adjudicated`, `id`). |
| `ADJUDICATION_REPORT.md` | Per-contested-item rulings, the soundness integrity-gate trace table, and the keymap correction. |
| `HUMAN_STUDY_REPORT.md` | **The reliability-study report** (5 annotators + calibration): Fleiss κ, per-annotator accuracy, panel-vs-gold (56/57, the IT0036 consensus error only the tool catches), effort. |
| `human_panel_gold.jsonl`, `human_vs_expert.json` | the adjudicated 5-panel gold (reproduces `gold.jsonl`) + its comparison (per-check majority accuracy, consensus-error list, τ ceilings, person-hours). |
| `pool/items.jsonl` | The **blinded** pool the annotators saw: opaque id, check, target, inlined sanitized Lean, informal spec, abstract theorem. No path/provenance/truth. |
| `pool/keymap.json` | **PRIVATE** key: id → path, source bucket, provenance, construction truth (+ the IT0036 correction with its original preserved). Never show to annotators. |
| `pool/raw_h1..h5.jsonl` | the five annotators' raw labels + reasons + confidence + time. |
| `pool/human_report_round{1,2,3,4}.json` | per-round κ/accuracy/timing snapshots (1–3 = 2-person calibration pilot; 4 = converged 5-person panel). |
| `../../scripts/build_annotation_pool.py` | Reproducibly rebuilds the blinded pool + keymap from the Lean sources (runbook §6). |
| `../../scripts/human_reliability.py`, `../../scripts/human_gold.py` | Recompute the 5-panel Fleiss κ / accuracy / timing and the adjudicated gold. |

Reproduce: `python scripts/human_reliability.py --round 4 --raters h1,h2,h3,h4,h5 && python scripts/human_gold.py`.

---

## The four sources in the pool (study §2)

- **gold (24)** — released `Example/*.lean` anchors: GD, PGD, ADMM, BCD. Mostly faithful; the
  ADMM (`Lasso_ADMM.toADMM`, `isLasso_KKT`) and BCD (`ProblemData`, `BCD`) instances are the
  **canonical hollow** cases (a condition field `sorry`).
- **planted (17)** — ground-truth-by-construction faults: 8 def-eq reference corruptions (check 1),
  6 single-field `by sorry` injections (check 2), the scratch hollow + wrong-rate variants.
- **regen (10)** — realistic regenerated SITA outputs (Least-squares / Ridge / Logistic /
  Quadratic GD): where the interesting *real* unfaithfulness lives.
- **mock (6)** — the hand-built faithful/hollow fixtures.

---

## Use it to calibrate new annotators

1. Give a new annotator the blinded `pool/items.jsonl` (or a 15–30 item subset of planted+gold).
   Have them label without seeing `gold.jsonl` or `keymap.json`.
2. Score against `gold.jsonl`. The **0.8 calibration gate** (study §4) is on the definitional and
   statement checks. If they fall short, walk the misses, then re-test on a fresh subset.

### Worked teaching examples (the cases that separate careful from sloppy)

- **Checks are orthogonal — a *sound* instance can sit on an *unfaithful* definition.**
  Quadratic-minimization regen: `def f := ½‖x − Qx − c‖²` is the **wrong objective** (target is
  ½xᵀQx + cᵀx) → *definitional = unfaithful*; yet the GD `instance` has no `sorry` in any field →
  *instance_soundness = faithful*; and the generic O(1/k) rate *statement = faithful*. Three checks,
  three verdicts on one file. Judge each check on its own target.

- **Soundness = trace the fields actually wired in, not the file's `sorry` count.**
  `Lasso.isProblem` (ADMM) is **sound** — an empty-`where` data instance — even though the *file*
  is full of `sorry` in unrelated lemmas (`uniq_subX/Y`, `feasible`, `slater`). Conversely
  `Lasso_ADMM.toADMM` is **hollow** because its `iter₁/iter₂/iter₃` ← `iter_cor1/2/3` and `hX/hY`
  ← `uniq_subX/uniq_subY` are all `sorry`. Follow each field to its proof.

- **Algebraically-equal rewrites are faithful; don't over-flag.**
  `½·z`, `z/2`, `2⁻¹·z`, `z·(1/2)` are the same number → *faithful*. Only a genuine change
  (`1/3`, dropped `½`, missing `^2`, `+b` vs `−b`) is *unfaithful*.

- **Statement faithfulness — order vs constant vs quantifier.** The hardest cases, by design:
  - `GD_wrongrate`: claims `1/(3(k+1)t)`, **strictly tighter** than the abstract `1/(2(k+1)t)` the
    proof `apply`s → an over-claim the abstract result can't give → **transfer-invalid AND
    statement-unfaithful**.
  - `hollow_lasso` theorem: `1/(k·t)` looks merely *looser* than `1/(2k·t)` — **but** the quantifier
    is widened `ℕ⁺ → ℕ`, so at `k=0` the Lean bound is `1/0 = 0`, asserting `target(x₀) − target(xm)
    ≤ 0` — **false** → **unfaithful**. The deciding move is checking the `k=0` corner.

- **A non-certifiable instance is not "faithful".** IT0036 names helper proofs (`update_cor`,
  `pos_l`) that are **absent from the artifact**, so its certificate cannot be exhibited. All five
  annotators called it `faithful`; the decidable gate marks it `unfaithful` and the construction key
  was corrected. Abstention/non-certification is scored as a recall miss, never as faithful (§7).

---

## Honest caveats (carry into the paper)

- **`#print axioms` not yet run on the built toolchain.** Soundness gold labels are from textual
  `sorry`-tracing of the real sources (unambiguous here — the tokens are visible); `#print axioms
  <target>` is the final confirmation of the integrity gate (study §7).
- **Contamination tags are `post-cutoff: unknown`** in `provenance` — set per source before the
  headline τ (study §2, RLM25 strategy).
- **57 items** is a calibration-grade reference set, below the 300–500 the full study targets. Scale
  with more regen trials via `build_annotation_pool.py` before the headline run.
- **Single-site panel** — five annotators from one group; consider an external annotator for the
  headline run.
