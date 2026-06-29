# Third-party components

This repository vendors a minimal snapshot of an upstream Lean project so that the symbolic
experiments are reproducible without a separate checkout. Our own contribution is everything
**outside** `Code/`; the contents of `Code/` are redistributed under their original licenses.

## `Code/lean/` — Optlib (+ autoformalization examples)

- **What:** the `Optlib` Lean 4 optimization library and the structure-to-instance
  autoformalization `Example`/`Template` files that the certifier runs on.
- **License:** Apache License 2.0 (see `Code/lean/LICENSE_Optlib.txt`).
- **Pinned dependency:** Mathlib `v4.13.0` (see `Code/lean/lake-manifest.json`); fetched at build
  time by `lake exe cache get` — **not** vendored here.
- **Source:** the released base autoformalization system (SITA) and the Optlib project.
- **Modifications:** none to the vendored files. The experiment scripts read these files and
  compile *temporary, in-memory* variants (e.g. planted `sorry`); the on-disk sources are
  unchanged. The `Regen_gd*` directories hold our regenerated outputs (our contribution), kept
  here only so `scripts/certify_regen.py` is reproducible.

Everything under `instance_beq/`, `scripts/`, `lean/InstanceBEq/`, `paper/`, `eval_logs/`,
`tests/`, and `docs/` is original to this work and released under the top-level `LICENSE` (MIT).
