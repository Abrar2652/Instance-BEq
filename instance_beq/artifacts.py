"""Parse a SITA-generated .lean file into structured declarations.

This is deliberately a *lightweight* slicer, not a Lean frontend: Lean itself is our semantic
oracle, so the parser only needs to (a) name each top-level declaration and (b) hand a focused
source slice to the oracle. It handles the constructs seen in real SITA output: `def/class/
instance/theorem/lemma/abbrev`, `where`-blocks and `:=`-bodies, multiline signatures, `local
notation`, `open`, `section`, and `variable`.

Robustness strategy: we split on top-level declaration keywords found at column 0 (Lean
top-level decls are unindented), then attribute each block's body by detecting `:=` / `where` /
`by`. This is good enough for slicing; the oracle does the real checking.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

DeclKind = Literal["def", "class", "instance", "theorem", "lemma", "abbrev"]

_DECL_KW = ("def", "class", "instance", "theorem", "lemma", "abbrev")
# A top-level declaration starts at column 0, optionally preceded by attributes/`noncomputable`/`private`.
_DECL_START = re.compile(
    r"^(?:@\[[^\]]*\]\s*)?"
    r"(?:noncomputable\s+|private\s+|protected\s+|partial\s+)*"
    r"(?P<kind>def|class|instance|theorem|lemma|abbrev)\s+(?P<name>[^\s:({\[]+)"
)
_IMPORT = re.compile(r"^import\s+(\S+)")
_OPEN = re.compile(r"^open\s+(.+)$")
_SECTION = re.compile(r"^(?:noncomputable\s+)?section\s+(\S+)")
_NOTATION = re.compile(r"^local\s+notation.*$")


@dataclass
class Decl:
    kind: DeclKind
    name: str
    signature: str
    body: str
    span: tuple[int, int]
    raw: str
    has_where: bool = False
    fields: list[str] = field(default_factory=list)  # for class/instance where-blocks

    def __repr__(self) -> str:  # concise for logs/tests
        return f"Decl({self.kind} {self.name} @{self.span})"


@dataclass
class ParsedArtifact:
    path: str
    imports: list[str] = field(default_factory=list)
    opens: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    local_notation: list[str] = field(default_factory=list)
    decls: list[Decl] = field(default_factory=list)
    informal: Optional[dict] = None
    abstract_structure: Optional[str] = None

    @property
    def defs(self) -> list[Decl]:
        return [d for d in self.decls if d.kind in ("def", "abbrev")]

    @property
    def classes(self) -> list[Decl]:
        return [d for d in self.decls if d.kind == "class"]

    @property
    def instances(self) -> list[Decl]:
        return [d for d in self.decls if d.kind == "instance"]

    @property
    def theorems(self) -> list[Decl]:
        return [d for d in self.decls if d.kind in ("theorem", "lemma")]


def _split_signature_body(block: str) -> tuple[str, str, bool, list[str]]:
    """Given a declaration block, separate signature from body.

    Returns (signature, body, has_where, fields).
    """
    # Find the first top-level ':=' or 'where' (not inside brackets).
    depth = 0
    i = 0
    n = len(block)
    where_idx = None
    assign_idx = None
    while i < n:
        c = block[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0:
            if block.startswith(":=", i):
                assign_idx = i
                break
            # 'where' as a word at depth 0
            if block.startswith("where", i) and (i == 0 or not block[i - 1].isalnum()) \
                    and (i + 5 >= n or not block[i + 5].isalnum()):
                where_idx = i
                break
        i += 1

    if where_idx is not None:
        sig = block[:where_idx].strip()
        body = block[where_idx + 5:].strip()
        fields = _parse_where_fields(body)
        return sig, body, True, fields
    if assign_idx is not None:
        sig = block[:assign_idx].strip()
        body = block[assign_idx + 2:].strip()
        return sig, body, False, []
    # no body (e.g. `class Foo (..)` with no where) -> all signature
    return block.strip(), "", False, []


def _parse_where_fields(where_body: str) -> list[str]:
    """Extract field names from a where-block. Fields are `name := expr` or `name : Type`."""
    fields = []
    for line in where_body.splitlines():
        s = line.strip()
        m = re.match(r"([A-Za-z_][A-Za-z0-9_'!?]*)\s*(:=|:)", s)
        if m:
            fields.append(m.group(1))
    return fields


def parse_lean_text(text: str, path: str = "<memory>") -> ParsedArtifact:
    lines = text.splitlines()
    art = ParsedArtifact(path=path)

    # First pass: headers
    for ln in lines:
        s = ln.strip()
        if m := _IMPORT.match(s):
            art.imports.append(m.group(1))
        elif m := _OPEN.match(s):
            art.opens.append(m.group(1).strip())
        elif m := _SECTION.match(s):
            art.sections.append(m.group(1))
        elif _NOTATION.match(s):
            art.local_notation.append(s)

    # Second pass: declaration blocks. A decl runs from its start line until the next top-level
    # decl start, `end`, or EOF.
    decl_starts: list[tuple[int, re.Match]] = []
    for idx, ln in enumerate(lines):
        m = _DECL_START.match(ln)
        if m:
            decl_starts.append((idx, m))

    for j, (start_idx, m) in enumerate(decl_starts):
        end_idx = decl_starts[j + 1][0] if j + 1 < len(decl_starts) else len(lines)
        # also stop early at an `end <section>` boundary at column 0
        for k in range(start_idx + 1, end_idx):
            if re.match(r"^end\b", lines[k]):
                end_idx = k
                break
        block = "\n".join(lines[start_idx:end_idx]).rstrip()
        sig, body, has_where, fields = _split_signature_body(block_after_keyword(block, m))
        art.decls.append(Decl(
            kind=m.group("kind"),  # type: ignore[arg-type]
            name=m.group("name"),
            signature=sig,
            body=body,
            span=(start_idx + 1, end_idx),  # 1-indexed inclusive-ish
            raw=block,
            has_where=has_where,
            fields=fields,
        ))
    return art


def block_after_keyword(block: str, m: re.Match) -> str:
    """Strip the leading `<modifiers> kind name` so signature parsing starts at the params."""
    # Remove everything up to and including the matched name on the first line.
    first_nl = block.find("\n")
    first_line = block if first_nl == -1 else block[:first_nl]
    rest = block[len(first_line):]
    # Re-find name end within first_line via the match end on the original line.
    name_end = m.end()
    return (first_line[name_end:] + rest).strip()


def parse_lean_file(path: str | Path) -> ParsedArtifact:
    p = Path(path)
    art = parse_lean_text(p.read_text(encoding="utf-8"), path=str(p))
    return art
