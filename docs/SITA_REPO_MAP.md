# SITA Repo Map (upstream)

Annotated map of the released SITA codebase (`SITA-main/`), based on reading the actual source.
This is what Instance-BEq plugs into. Paths are relative to `SITA-main/`.

## Top level

```
Code/
├── src/            # Python pipeline (the brain)
├── data/           # configs, problems, theorem DB, error knowledge base
├── lean/           # Lean 4 project (Optlib + autoformalization templates/examples/outputs)
└── tool/           # model_downloader.py (downloads the local error-classifier model)
fig/                # pipeline diagram
README.md, LICENSE
```

## The pipeline (6 steps), driven by `Code/src/main.py`

`LeanPipeline.run_complete_pipeline()` runs:

1. **Generation** — `first_generation.process_all_problems(...)`: for each problem in the JSONL,
   prompt the LLM with (structure template + gold example + problem) → write a Lean file →
   rule-fix → compile → record errors. `initial_generations = 3` trials per problem.
2. **First error correction** — `automatic_fixer.correct_all_trials_in_folder(lean_root, ...)`:
   feedback-driven fixer using the error knowledge base.
3. **Extract fixed files** — copies `*_fixed.lean` into a parallel `<root>_fixed/` tree.
4. **Proof generation** — `process_all_lean_files_parallel(...)` →
   `first_generation.process_all_problems_proof(...)`: replace `sorry` with proofs (3 trials).
5. **Second error correction** — `parallel_correct_all(...)` over each subfolder's `Proof/` dir.
6. **Harmless fixing** — `collect_best_proof_trials(...)` picks the best trial per index, then
   `LeanErrorCorrector.fix_errors()` inserts `sorry` where needed to guarantee a clean-compiling
   file (this is why "type-checks" ≠ "faithful": step 6 can re-insert `sorry`).

**Output of interest to us:** the `ProofTrialFinal/*.lean` files — the final certified-by-SITA
artifacts. Instance-BEq runs here.

## Key source files (what each does, and what we reuse)

### `src/interact.py`  ← **WE REUSE THIS (Lean oracle)**
- `compile_file(filepath, cwd="lean") -> (basename, stdout, returncode)`
  Runs `subprocess.run(["lake", "env", "lean", filepath], cwd=cwd, ...)`. This is the *only*
  way the repo invokes Lean. Our `harness/lean_oracle.py` wraps exactly this.
- `parse_lean_output_with_context(stdout) -> (warnings, errors)`
  Regex-parses Lean's `file:line:col: error|warning: msg`, attaches the offending source line.
  Returns lists of dicts: `{line, column, message, line_content, char_at_column}`.
  **Note:** it parses *textual* Lean output. It does NOT detect `sorry` (which surfaces as a
  *warning* "declaration uses 'sorry'", not an error). Our SorryDetect work extends this.

### `src/first_generation.py`  ← **WE REUSE THE LLM WRAPPER**
- `CONFIG`: `model_name="deepseek-reasoner"`, `temperature=0.7`, `initial_generations=3`,
  `proof_generations=3`. Reads `data/api/config.json` for `api_key` + `base_url`.
- `call_deepseek_api(prompt, logger) -> str`: single-shot chat completion. Our `harness/llm.py`
  wraps this (or re-implements the same OpenAI-client pattern with the same config) for
  reference-def generation and back-translation.
- `extract_lean_code(raw, logger)`: strips ```` ```lean / ```lean4 ```` fences. Reuse for parsing
  LLM-produced Lean.
- `generate_initial_version(...)`: builds the generation prompt (structure + example + problem).
  The prompt explicitly says "Replace All proofs with `sorry`" in the skeleton phase — confirming
  that *statements first, proofs later* is the design, and statements can be wrong independently
  of proofs.
- `analyze_sorry_positions(content) -> (contexts, count)`: regexes
  `(theorem|lemma|def|instance)\s+name : sig := sorry`. Useful prior art for our artifact parser,
  but note it only catches the `:= sorry` form, not tactic-block `sorry` or transitive `sorry`.
- `generate_initial_proof_version(...)`: the proof-filling prompt.

### `src/automatic_fixer.py`
The feedback-driven corrector. `LeanErrorCorrector` class; `correct_all_trials_in_folder`,
`fix_all_trials_in_folder`. Uses the error knowledge base. We don't modify it, but Direction 2
(self-improving engine) would hook here.

### `src/rulebased_fixer.py`
`process_lean_file(path, inplace=True)`: deterministic syntactic fixes (notation, unused
hypotheses, formatting). Pure preprocessing; safe to call, we don't change it.

### `src/majorty_voting.py`  ← **BASELINE B SOURCE**
SITA's semantic check: sample the file's quality from multiple LLM votes (DeepSeek-V3, T=0.7,
16 rounds in the paper), scoring problem formalization / algorithm correctness / update-scheme
explicitness / theoretical analysis / proof completion. Our `baselines/majority_voting.py`
mirrors this so we compare against SITA's own faithfulness proxy.

### `src/backtranslation.py`  ← **REUSE FOR CHECK 3b**
Maps formal Lean back to natural language. We reuse the approach for the statement-faithfulness
sub-check (back-translate instance theorem → symbolic-compare to informal claim).

### `src/direct_generation.py`, `src/cleaner.py`
Direct (no-pipeline) generation baseline; output cleaner. Not central for us.

## Data formats (so the artifact parser matches reality)

### `data/problem/problem_test.jsonl` — one JSON object per line
```json
{
  "problem_name": "Lasso problem",
  "problem_statement": "\\min_{x} \\frac{1}{2}\\|Ax-b\\|^2 + \\mu\\|x\\|_1.",
  "class": "proximal gradient",
  "algorithm": "Let f(x)=..., h(x)=...; prox_{t h}(x)=sign(x)max{|x|-tμ,0}; iterate y^k=..., x^{k+1}=..."
}
```
Fields: `problem_name`, `problem_statement` (LaTeX), `class` (which abstract structure),
`algorithm` (the update scheme in LaTeX). The informal "ground truth" our checks compare against
lives here.

### `data/api/config.json`
`{ "api_key": "...", "base_url": "..." }` — DeepSeek-compatible OpenAI endpoint. **Gitignored.**

### `data/bugfix/error_knowledge.json` — list of 75 entries
```json
{
  "error_type": "unexpected token",
  "error_message": "unexpected token 'λ'; expected '_' or identifier",
  "context": "class error_example ... (λ : Fin n → ℝ) ...",
  "successful_fixes": ["... (lam : Fin n → ℝ) ..."],
  "fix_suggestion": "Replace λ with lamb"
}
```
Retrieval-augmented fix knowledge. Direction 2 would grow this with faithfulness fixes.

### `data/theorem_database/Optlib/*.json` — formalized abstract theorems, per Optlib module
Each file is a list of entries:
```json
{
  "theorem_name": "prox_prop",
  "theorem_statement": " (f : E → ℝ) (x : E) (xm : E) : Prop",
  "variable": ["variable {E : Type*}", "variable [NormedAddCommGroup E]", ...],
  "namespaces": ["Filter", "Topology", "InnerProductSpace", "Set"],
  "proof_process": "def prox_prop ... := IsMinOn ...",
  "type": "definition",            // or "theorem"/"lemma"
  "filename": "Proximal"
}
```
Modules present: `Proximal, KL, Lsmooth, L1Space, MinimaClosedFunction, ConvexFunction,
StronglyConvex, Subgradient, BanachSubgradient, Subdifferential, Calculation, Lemmas,
OptimalityConditionOfUnconstrainedProblem`. This is the retrieval corpus for check 1's
reference characterizations.

## Lean project (`Code/lean/`)

- `lean-toolchain`: `leanprover/lean4:v4.13.0`. `lakefile.lean`: requires Mathlib `v4.13.0`.
- `Optlib/Autoformalization/Template/*.lean` — **abstract structures** (the "S" in
  structure-to-instance). E.g. `GD_template.lean` defines `unconstrained_problem`,
  `Gradient_Descent`, and the abstract `gradient_method_convergence` lemma (body `sorry` in the
  template — it's proven elsewhere in Optlib; the template is the interface).
- `Optlib/Autoformalization/Example/*.lean` — **gold instances** (the "I"). `GD_example.lean`
  formalizes LeastSquares: `LeastSquares_problem` (with `def .f`, `def .l`), the
  `instance LeastSquares_problem.unconstrained_problem`, `LeastSquares_GD`, the bridging
  `instance LeastSquares_GD.Gradient_Descent` (all fields discharged by real lemmas:
  `update_cor`, `pos_l`, `ht`, `initial` — NO sorry), and the transferred theorems
  `LeastSquares_GD.point_descent` / `.gradient_method` (proven by `apply`ing the abstract
  lemmas). **This file is the canonical example for all three Instance-BEq checks.**
- Templates exist for: `GD, PGD, BCD, ADMM, NesterovFirst, NesterovSecond`. Examples likewise.
- Generated outputs go under `Optlib/Autoformalization/R1/` (and similar), then `*_fixed/`,
  then `ProofTrialFinal/`.

## The faithfulness gap, located precisely in this code

- Step 6 (`main.py`) can re-insert `sorry` to force clean compilation → "type-checks" is weak.
- `instance ... where` fields can be `sorry` (the template's abstract lemma is `sorry`-bodied by
  design) → an instance can be **hollow**.
- `parse_lean_output_with_context` reports `error`s, and `sorry` is a *warning* → SITA's success
  metric (zero errors) does not penalize `sorry`. Our SorryDetect closes this.
- Nothing in the pipeline checks the generated `def` against the informal object, nor the
  transferred theorem's *statement* against the informal claim. Those are checks 1 and 3b.
