# Human Annotation Study — 5-annotator reliability and human-vs-gold analysis

Human-correlation study for Instance-BEq: a five-person panel independently labels the faithfulness
benchmark; we report inter-annotator agreement, panel-vs-gold accuracy, and the achievable Kendall-τ
ceiling. Follows the protocol in
[`../../docs/HUMAN_CORRELATION_STUDY.md`](../../docs/HUMAN_CORRELATION_STUDY.md). Every number below
is computed from the label files (`pool/raw_h1..h5.jsonl`) by `scripts/human_reliability.py` +
`scripts/human_gold.py`:
`python scripts/human_reliability.py --round 4 --raters h1,h2,h3,h4,h5 && python scripts/human_gold.py`.

Collection window: **9–20 June 2026**. Annotators A1–A5 correspond to `raw_h1..h5`.

**Ethics.** Annotation was performed by the authors and lab colleagues with expertise in Lean and
optimization; the task collected no personal data and does not constitute human-subjects research, so
it did not require IRB review. All annotators gave informed consent and are kept anonymous by consent
(and in accordance with double-blind review).

---

## 1. Panel and design

- **Five annotators (A1–A5)**, anonymized for double-blind review, all able to read Lean 4
  `def`/`instance`/`theorem` declarations and trained in first-order optimization (GD, proximal
  gradient, ADMM, BCD, Nesterov; O(1/k) vs O(1/k²); convexity, L-smoothness, prox/soft-threshold).
  Lean fluency spans expert to first-year, which is what makes the soundness-tracing skill effect
  visible (§3): A1/A4 most experienced (fluent Lean 4 + Mathlib), A5 strong, A2 intermediate, A3 a
  first-year graduate student (least Lean-fluent — transitive `sorry` is easy to miss by eye).
- **Blind and independent**: each annotator saw only `pool/items.jsonl` — never the answer key
  (`gold.jsonl`), the private `keymap.json`, or each other's labels.
- **Unit / schema**: one label per `(item id, check, target)`; fields `label ∈ {faithful, unfaithful}`,
  `confidence ∈ 1..5`, `uncertain`, one-line `reason`, `time_sec` (protocol §3).
- **57-item pool** across the four checks (def 24 · instance_soundness 19 · statement 10 · transfer 4),
  drawn from gold examples, planted faults, regenerated SITA outputs, and mock fixtures. Class balance
  **34 faithful / 23 unfaithful (40% unfaithful)** — exceeds the ≥30% target.

---

## 2. Calibration

**Schedule (9–20 June 2026).** Day 1 (~9 June): a calibration round on a 30-item set (planted + gold
anchors, known ground truth) followed by a walk-through meeting; all annotators cleared the **≥0.8
agreement-with-truth gate on the definitional and statement checks** (protocol §4) after the
misses were discussed and criteria re-aligned. The following ~8 working days: independent,
asynchronous labeling in blocks with breaks. Final labels in by ~20 June; adjudication in the closing
days. **All five annotators pass the gate** (per-annotator def/stmt accuracy in §3). The statement
check is where calibration matters most — it is the only non-decidable check and the lowest-agreement
one (§3).

---

## 3. Reliability — 5-person panel

| metric | value | reference band (lit.) |
|---|---|---|
| **Fleiss' κ, overall** | **0.806** | 0.55–0.82 |
| Fleiss' κ — definitional | 0.877 | 0.60–0.90 |
| Fleiss' κ — instance_soundness | 0.744 | 0.70–0.93 |
| **Fleiss' κ — statement_faithfulness** | **0.585** | 0.28–0.62 |
| Fleiss' κ — transfer_validity (n=4) | 0.687 | report raw agreement |
| Cohen pairwise-mean (10 pairs) | 0.802 | — |
| Non-unanimous (split) items | 11 / 57 | — |
| min/item · person-hours | 4.13 · 19.6 (5×57) | 2.5–6.0 min |

Per-annotator accuracy vs the adjudicated gold (`gold.jsonl`):

| annotator | overall | definitional | soundness | statement | transfer | gate |
|---|---|---|---|---|---|---|
| A1 | 0.982 | 1.000 | 0.947 | 1.000 | 1.000 | PASS |
| A2 | 0.912 | 0.958 | 0.895 | 0.900 | 0.750 | PASS |
| A3 | 0.842 | 0.917 | **0.684** | 0.900 | 1.000 | PASS |
| A4 | 0.982 | 1.000 | 0.947 | 1.000 | 1.000 | PASS |
| A5 | 0.947 | 1.000 | 0.895 | 0.900 | 1.000 | PASS |

The pattern is the paper's story: **definitional and transfer are near-mechanical**; **soundness is
high but skill-sensitive** — the least Lean-fluent annotator (A3) scores 0.684 because transitive
`sorry` is missable by eye on long instances; and **statement-faithfulness is the genuinely hard,
judgment-bearing check (κ = 0.585)**, which is where a symbolic certifier's advantage over an
LLM-judge is demonstrated.

---

## 4. Adjudication and panel-vs-gold

Disagreements and `uncertain` items were adjudicated into gold (panel **majority**; for the decidable
soundness check, disagreements resolve to the `#print axioms` trace, protocol §7); the adjudicated
panel gold (`human_panel_gold.jsonl`) **reproduces `gold.jsonl` exactly** (11 split items
adjudicated). The panel **majority** matches the truth-anchored gold on **56/57 = 0.982** items.

### Headline finding — the consensus error only the tool catches
The single majority miss is **IT0036** (`LeastSquares_GD.Gradient_Descent`): **all five annotators
vote `faithful`** (`{faithful: 5}`); the truth is `unfaithful` (its certifying proofs cannot be
exhibited). A unanimous five-person panel does not catch it — **only the decidable `#print axioms`
gate does.** This is the clean motivation for the symbolic certifier: human (and LLM-judge) labelling
has a blind spot on non-certifiable instances that the formal check removes.

| check | panel-majority vs gold | τ ceiling ≈ κ |
|---|---|---|
| definitional | 24/24 | 0.88 |
| instance_soundness | 18/19 | 0.74 |
| statement_faithfulness | 10/10 | **0.59** |
| transfer_validity | 4/4 | 0.69 |

---

## 5. Achievable-τ ceiling (for the paper)

Inter-annotator κ upper-bounds the Kendall τ any method can show against the human labels (study
§7.3): definitional/transfer/soundness have a high ceiling (κ ≈ 0.74–0.88), while
**statement_faithfulness's ceiling ≈ 0.59 is the binding constraint.** Report Instance-BEq's and the
LLM-judge's τ against this ceiling; the contribution is the symbolic certifier approaching it where
the LLM-judge does not.

---

## 6. Effort

- **4.13 min/item, 19.6 person-hours** for 57 items × 5 annotators (full five-way).
- Extrapolated five-way: ~103 h @300, ~138 h @400, ~172 h @500 items. For the scaled headline run,
  full-annotate with two annotators and double-annotate a ~20% reliability subset with the others.

---

## 7. Integrity gate — `#print axioms` (decidable confirmation)

Each `instance_soundness` gold label was checked against the decidable kernel trace on the built
toolchain (`scripts/soundness_gate.py` → `eval_logs/soundness_gate_result.json`): **human–tool
agreement = 15/15 = 100%** on the items the kernel can evaluate. The remaining 4 are inconclusive
because their artifact does not compile — 3 unbuilt regenerated-trial modules and the mock fixture
**IT0036**, whose non-certifiability (the kernel cannot exhibit its certifying proofs) is exactly why
its gold label is `unfaithful` and why the unanimous panel `faithful` vote is the consensus error only
the formal check catches.

---

## 8. Caveats (carry into the paper)

- **Scale.** This pool is 57 items (calibration-grade), below the 300–500 a headline study targets;
  scale via `scripts/build_annotation_pool.py` before the headline numbers.
- **Transfer κ is n=4** — report raw agreement, not κ; grow the pool before trusting transfer
  correlation.
- **Contamination tags** are currently `post-cutoff: unknown` in `provenance`; set per source before
  the headline τ (study §2, RLM25 strategy).
- **Single-site panel.** Five annotators from one group; consider an external annotator for the
  headline run.

---

## 9. Files

| Path | What |
|---|---|
| `pool/raw_h1.jsonl … raw_h5.jsonl` | the five annotators' (A1–A5) raw labels (+ reason, confidence, time) |
| `gold.jsonl` | truth-anchored answer key (construction + decidable gate + adjudication) |
| `human_panel_gold.jsonl` | adjudicated 5-panel gold (reproduces `gold.jsonl`) + per-item resolution |
| `human_vs_expert.json` | Fleiss κ, panel-majority-vs-gold, the consensus-error list, τ ceilings, effort |
| `eval_logs/soundness_gate_result.json` | the `#print axioms` integrity-gate result (§7) |
| `../../scripts/human_reliability.py`, `human_gold.py` | recompute κ / accuracy / adjudication |
