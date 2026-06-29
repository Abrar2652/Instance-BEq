"""Lean oracle: the single point through which Instance-BEq talks to Lean.

Real mode shells out to `lake env lean` via SITA's `interact.compile_file`. Mock mode returns
canned results from a fixture DB so the whole test suite runs with no Lean and no network.

Keeping ALL Lean access behind this class is what makes mock mode possible (the design notes guardrail
#4). No check may invoke Lean directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from instance_beq.config import InstanceBEqConfig, DEFAULT, SORRY_TOKENS

# Reuse SITA's parser if importable; otherwise fall back to a local copy of the same regex.
_WARN_RE = re.compile(r"(.+):(\d+):(\d+): warning: (.+)")
_ERR_RE = re.compile(r"(.+):(\d+):(\d+): error: (.+)")
_SORRY_WARN = re.compile(r"declaration uses '?sorry'?")
# Custom `#faithful_axioms` command (SorryDetect.lean) emits: AXIOMS <name> :: [..]
_AXIOMS_LINE = re.compile(r"AXIOMS\s+(\S+)\s+::\s+(.*)")
# Native built-in `#print axioms <name>` emits one of:
#   'Foo.bar' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
#   'Foo.bar' does not depend on any axioms
# Verified working on Lean v4.13.0 (2026-06-22); this is the PRIMARY mechanism — always in
# scope, transitive, no custom command needed.
# DOTALL + non-greedy: Lean's pretty-printer wraps long axiom lists across multiple lines
# (e.g. for long declaration names), so the closing `]` may not be on the opening line.
_AXIOMS_PRINT = re.compile(r"'([^']+)' depends on axioms: \[(.*?)\]", re.DOTALL)
_AXIOMS_NONE = re.compile(r"'([^']+)' does not depend on any axioms")


@dataclass
class OracleResult:
    ok: bool                       # zero errors
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    raw: str = ""
    uses_sorry: bool = False       # warning OR transitive (via #faithful_axioms)
    axioms: dict[str, list[str]] = field(default_factory=dict)  # decl -> axiom list
    mock: bool = False

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "uses_sorry": self.uses_sorry,
            "axioms": self.axioms,
            "mock": self.mock,
        }


def _parse_lean_output(text: str) -> tuple[list[dict], list[dict]]:
    """Local re-implementation of SITA interact.parse_lean_output_with_context (text-only)."""
    warnings: list[dict] = []
    errors: list[dict] = []
    current: Optional[dict] = None
    is_warn = False

    def flush():
        nonlocal current
        if current is None:
            return
        (warnings if is_warn else errors).append(current)
        current = None

    for line in text.splitlines():
        w = _WARN_RE.match(line)
        e = _ERR_RE.match(line)
        if w or e:
            flush()
            fp, ln, col, msg = (w or e).groups()
            current = {"filepath": fp.strip(), "line": int(ln), "column": int(col),
                       "message": msg.strip()}
            is_warn = bool(w)
        elif current is not None:
            current["message"] += "\n" + line.strip()
    flush()
    return warnings, errors


def _parse_axioms(text: str) -> dict[str, list[str]]:
    """Parse axiom-closure lines from either the native `#print axioms` output (primary) or the
    custom `#faithful_axioms` command (secondary). Both are merged into {decl: [axioms]}."""
    out: dict[str, list[str]] = {}

    def _split(rest: str) -> list[str]:
        return [a.strip().strip("[],") for a in rest.split(",") if a.strip().strip("[],")]

    # native `#print axioms` — primary
    for m in _AXIOMS_PRINT.finditer(text):
        out[m.group(1)] = _split(m.group(2))
    for m in _AXIOMS_NONE.finditer(text):
        out.setdefault(m.group(1), [])
    # custom `#faithful_axioms` — secondary (does not overwrite a native result)
    for m in _AXIOMS_LINE.finditer(text):
        decl, rest = m.group(1), m.group(2)
        if rest.strip() == "[UNKNOWN_CONSTANT]":
            out.setdefault(decl, ["UNKNOWN_CONSTANT"])
        else:
            out.setdefault(decl, _split(rest))
    return out


class LeanOracle:
    def __init__(self, cfg: InstanceBEqConfig = DEFAULT, mock_db: dict | None = None):
        self.cfg = cfg
        self.mock = cfg.mock
        self._mock_db = mock_db or {}

    # ---- mock plumbing -----------------------------------------------------
    @staticmethod
    def _tag(source: str) -> str:
        """A fixture key. Prefer an explicit `-- @mock:<key>` tag; else hash the source."""
        m = re.search(r"--\s*@mock:(\S+)", source)
        if m:
            return m.group(1)
        return "h:" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]

    def _mock_lookup(self, source: str) -> OracleResult:
        key = self._tag(source)
        if key not in self._mock_db:
            raise KeyError(
                f"Mock oracle has no fixture for key {key!r}. Add it to the mock DB "
                f"(tests/mock_data/oracle_db.json) or tag the snippet with `-- @mock:<key>`."
            )
        d = self._mock_db[key]
        return OracleResult(
            ok=d.get("ok", not d.get("errors")),
            errors=d.get("errors", []),
            warnings=d.get("warnings", []),
            raw=d.get("raw", ""),
            uses_sorry=d.get("uses_sorry", False),
            axioms=d.get("axioms", {}),
            mock=True,
        )

    # ---- public API --------------------------------------------------------
    def check_file(self, path: str | Path) -> OracleResult:
        if self.mock:
            return self._mock_lookup(Path(path).read_text(encoding="utf-8"))
        return self._compile_path(Path(path))

    def check_snippet(self, lean_source: str, imports: list[str] | None = None) -> OracleResult:
        if self.mock:
            return self._mock_lookup(lean_source)
        header = "\n".join(imports or [])
        full = (header + "\n\n" + lean_source) if header else lean_source
        self.cfg.scratch_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".lean", dir=self.cfg.scratch_dir, delete=False, encoding="utf-8"
        ) as fh:
            fh.write(full)
            tmp = Path(fh.name)
        try:
            return self._compile_path(tmp)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

    # ---- real compilation --------------------------------------------------
    def _compile_path(self, path: Path) -> OracleResult:
        proc = subprocess.run(
            ["lake", "env", "lean", str(path.resolve())],
            cwd=str(self.cfg.lean_cwd.resolve()),
            capture_output=True, text=True, encoding="utf-8",
        )
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        warnings, errors = _parse_lean_output(text)
        uses_sorry = any(_SORRY_WARN.search(w["message"]) for w in warnings)
        axioms = _parse_axioms(text)
        # transitive sorry via #faithful_axioms output
        for decl, axs in axioms.items():
            if any(tok in ax for ax in axs for tok in SORRY_TOKENS):
                uses_sorry = True
        return OracleResult(
            ok=(len(errors) == 0 and proc.returncode == 0),
            errors=errors, warnings=warnings, raw=text,
            uses_sorry=uses_sorry, axioms=axioms, mock=False,
        )


def load_mock_db(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
