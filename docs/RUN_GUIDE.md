# RUN GUIDE

How to set up, run mock (no Lean/no network), and run real (cluster) experiments, and how to
reproduce every number in the paper.

---

## 0. TL;DR

```bash
# mock mode — proves the wiring, needs neither Lean nor an API key, runs in seconds
pip install -r requirements.txt
pytest -q                              # full suite, green on mock data
python -m instance_beq.eval.run_certifier --inputs tests/mock_data/artifacts --mode mock

# real mode — on the cluster, after building Optlib and setting the API key
cd Code/lean && lake exe cache get && lake build && cd ../..
cp Code/data/api/config.example.json Code/data/api/config.json   # then edit in your key
python -m instance_beq.eval.run_certifier --inputs <SITA_output_dir> --mode real
```

## 1. Environment

### Python
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
`requirements.txt`: `openai pydantic pytest tqdm numpy pandas scipy`.

### Lean / Mathlib / Optlib (real mode only)
- Toolchain pinned by `Code/lean/lean-toolchain` → `leanprover/lean4:v4.13.0`. Install via
  `elan` (it will read the toolchain file automatically). **Do not** install a different Lean.
- Build (cache first — this avoids compiling Mathlib for hours):
  ```bash
  cd Code/lean
  lake exe cache get      # pulls prebuilt Mathlib oleans for v4.13.0
  lake build              # builds Optlib + our InstanceBEq lean target
  ```
- Smoke test the oracle:
  ```bash
  echo 'import Optlib\n#check @gradient_method_convergence' > /tmp/smoke.lean
  cd Code/lean && lake env lean /tmp/smoke.lean    # should print the type, no errors
  ```

### API key
- `Code/data/api/config.json` = `{ "api_key": "...", "base_url": "..." }`, DeepSeek-compatible.
- Gitignored. Use `config.example.json` as the template. Real LLM calls happen only in real mode
  and only for: check-1 reference-def (option b), check-3b back-translation, baseline C.

## 2. Mock vs Real — the switch

Everything is gated by `--mode {mock,real}` (and `InstanceBEqConfig.mock`):
- **mock**: `LeanOracle` and `LLMClient` return canned results from `tests/mock_data/*.json`
  keyed by snippet/prompt tag. No subprocess, no network. Deterministic. This is what CI runs and
  what proves the pipeline is correctly wired *before* you spend cluster hours.
- **real**: `LeanOracle` shells out to `lake env lean`; `LLMClient` calls the API.

A mock number is always tagged `"mock": true` in its output JSON and is **never** allowed into a
paper table (a repo guardrail). `metrics.py` refuses to emit a final table from mock runs
unless `--allow-mock-table` is passed (for pipeline debugging only).

## 3. Reproduction recipe (paper numbers)

Each step writes to `instance_beq/eval/results/<run_id>/` and prints the exact table/figure it
feeds.

1. **Generate SITA outputs** (if not already present). Standard SITA run:
   ```bash
   cd Code && python src/main.py --run-pipeline --problem-file data/problem/problem_test.jsonl
   ```
   Collect the `ProofTrialFinal/*.lean` artifacts.
2. **Certify**:
   ```bash
   python -m instance_beq.eval.run_certifier --inputs Code/lean/.../ProofTrialFinal --mode real
   ```
   → per-artifact certificates + `summary.json` (feeds the motivating "% hollow" statistic).
3. **Run baselines**:
   ```bash
   python -m instance_beq.eval.run_baselines --inputs <same> --mode real --which A B C
   ```
4. **Score against human gold**:
   ```bash
   python -m instance_beq.eval.metrics --gold annotation/gold.jsonl --runs <run_ids...>
   ```
   → Table (precision/recall/F1 per check + overall), Kendall-τ row, calibration plot for 3b.
5. **Ablations**:
   ```bash
   python -m instance_beq.eval.run_certifier --inputs <...> --mode real \
       --ablate {tactic_ensemble_size, no_bidirectional, no_retrieval, refdef_source}
   ```

## 4. Slurm

`scripts/slurm_certify.sh` is an array job — one artifact per task, symbolic checks are CPU-bound:
```bash
#!/bin/bash
#SBATCH --job-name=ibeq-certify
#SBATCH --array=0-499%32          # 500 artifacts, 32 concurrent
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/ibeq_%A_%a.out
source .venv/bin/activate
ARTIFACT=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" artifact_list.txt)
python -m instance_beq.eval.run_certifier --inputs "$ARTIFACT" --mode real --single
```
- GPU only needed for `Code/tool/model_downloader.py`'s error classifier (a separate, optional
  job). The certifier itself wants CPUs + network, not GPUs.
- Each task compiles snippets against the prebuilt Optlib — so **build once on a login/build node,
  share the `.lake` cache**, then array tasks reuse it read-only.

## 5. Caching & resumability

- LLM responses cached under `instance_beq/eval/results/_llm_cache/` keyed by
  `sha256(prompt|model|temp)`. Safe to re-run; cache hits are free.
- `run_certifier --resume` skips artifacts with an existing certificate JSON.
- Lean compile results are *not* cached across code changes (a tactic-ensemble change can flip a
  verdict); they are cached within a run via the snippet hash.

## 6. Common pitfalls

- **"unknown constant gradient_method_convergence"** → Optlib not built or wrong cwd. The oracle
  must run with `cwd=Code/lean`. Check `lake build` succeeded.
- **Mathlib cache miss → 3-hour build** → you bumped a version or `elan` picked a different
  toolchain. Verify `lean-toolchain` and `lakefile.lean` are untouched (guardrail #1).
- **`sorry` not detected** → you relied on the warning string; use `#faithful_axioms` (SorryDetect)
  for transitive sorry. See DESIGN §5.
- **Mock test needs network** → a check bypassed the oracle/LLM abstraction. All Lean/LLM access
  must go through `harness/lean_oracle.py` / `harness/llm.py` so mock mode can intercept it.
