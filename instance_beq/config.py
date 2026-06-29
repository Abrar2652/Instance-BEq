"""Central configuration for Instance-BEq.

All paths are resolved relative to the SITA repo root by default, but every field can be
overridden. Keeping this in one place means the implementation never hard-codes a path in a check.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _default_sita_root() -> Path:
    # Allow override via env; otherwise assume this package sits beside the SITA `Code/` tree.
    env = os.environ.get("SITA_ROOT")
    if env:
        return Path(env).resolve()
    # …/Instance-BEq/instance_beq/config.py — the SITA `Code/` tree may sit INSIDE the repo
    # (parents[1]) or beside it (parents[2]/[3]). Check inside-first.
    here = Path(__file__).resolve()
    candidates = [here.parents[1]]
    if len(here.parents) > 2:
        candidates.append(here.parents[2])
    if len(here.parents) > 3:
        candidates.append(here.parents[3])
    for up in candidates:
        if (up / "Code" / "lean").exists():
            return up
    return here.parents[1]


# Mathlib-standard axioms. Anything else in a proof's closure (esp. `sorryAx`) => unsound.
ALLOWED_AXIOMS: tuple[str, ...] = ("propext", "Classical.choice", "Quot.sound")

# Tokens that mean "this proof is fake".
SORRY_TOKENS: tuple[str, ...] = ("sorryAx", "sorry", "admit")


@dataclass
class InstanceBEqConfig:
    sita_root: Path = field(default_factory=_default_sita_root)
    mock: bool = False

    # LLM (mirrors SITA's first_generation.CONFIG)
    model_name: str = "deepseek-reasoner"
    temperature: float = 0.7
    llm_cache_dir: Path | None = None

    # check-1 reference-def source: "retrieval" | "llm" | "property"
    refdef_source: str = "retrieval"
    # three-way verdicts: if True, a check may return verdict "unknown" instead of forcing a bool
    allow_unknown: bool = True
    # tactic ensemble for definitional / equivalence checks, tried in order
    tactic_ensemble: tuple[str, ...] = (
        "rfl",
        "simp only [{lhs}, {rhs}]",
        "unfold {lhs} {rhs}; ring",
        "unfold {lhs} {rhs}; ext x; ring_nf; simp",
        "decide",
    )

    allowed_axioms: tuple[str, ...] = ALLOWED_AXIOMS

    @property
    def lean_cwd(self) -> Path:
        return self.sita_root / "Code" / "lean"

    @property
    def scratch_dir(self) -> Path:
        return self.lean_cwd / "Optlib" / "Autoformalization" / "_scratch"

    @property
    def theorem_db_dir(self) -> Path:
        return self.sita_root / "Code" / "data" / "theorem_database" / "Optlib"

    @property
    def api_config_path(self) -> Path:
        return self.sita_root / "Code" / "data" / "api" / "config.json"

    @property
    def templates_dir(self) -> Path:
        return self.lean_cwd / "Optlib" / "Autoformalization" / "Template"

    @property
    def examples_dir(self) -> Path:
        return self.lean_cwd / "Optlib" / "Autoformalization" / "Example"


DEFAULT = InstanceBEqConfig()
