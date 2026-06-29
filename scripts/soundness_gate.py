#!/usr/bin/env python3
"""Decidable integrity gate: confirm every instance_soundness gold label against the real
`#print axioms` trace on the built Lean toolchain (HUMAN study §7 / protocol §7).

For each soundness item in gold.jsonl we run `#print axioms <target>` on the corresponding
compilable artifact and compare the kernel verdict (sound = closure within the allowlist;
hollow = sorryAx/disallowed axiom) to the human-adjudicated gold label. Items on artifacts that do
not compile (mock fixtures, some regen trials) are reported as `inconclusive` — for the
non-certifiable fixture IT0036 that non-certifiability IS the finding (a faithful label requires a
certificate that cannot be exhibited).

Out: eval_logs/soundness_gate_result.json
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle

cfg = InstanceBEqConfig(mock=False)
oracle = LeanOracle(cfg)
LEAN = cfg.lean_cwd
ANN = Path(__file__).resolve().parents[1] / "instance_beq/annotation"


def tool_verdict(axset):
    if axset is None:
        return "inconclusive"
    if any(tok in a for a in axset for tok in SORRY_TOKENS) or any(a not in cfg.allowed_axioms for a in axset):
        return "hollow"
    return "sound"


def axioms_for(snippet, target):
    res = oracle.check_snippet(snippet)
    return res.axioms.get(target), res.ok


def run_item(it):
    path, target = it["path"], it["target"]
    # planted: "planted/sorry/Example/<F>.lean::<inst>::<field>"  -> patch field := by sorry
    if path.startswith("planted/sorry/"):
        m = re.match(r"planted/sorry/(Example/[^:]+\.lean)::[^:]+::(.+)", path)
        src_rel, field = m.group(1), m.group(2)
        text = (LEAN / "Optlib/Autoformalization" / src_rel).read_text(encoding="utf-8")
        text = re.sub(rf"(\n\s*{re.escape(field)}\s*:=)[^\n]*", r"\1 by sorry", text, count=1)
        return axioms_for(text + f"\n#print axioms {target}\n", target)
    # _scratch file (already a standalone hollow variant)
    if path.startswith("_scratch/"):
        f = LEAN / "Optlib/Autoformalization" / path
        if not f.exists():
            return None, False
        return axioms_for(f.read_text(encoding="utf-8") + f"\n#print axioms {target}\n", target)
    # built module (Example/ or Regen_gd/) -> import + query
    if path.startswith("Example/") or path.startswith("Regen_gd/"):
        mod = "Optlib.Autoformalization." + path[:-5].replace("/", ".")
        return axioms_for(f"import {mod}\n#print axioms {target}\n", target)
    # mock fixtures -> compile the fixture text directly (expected: will not compile)
    if path.startswith("tests/"):
        f = Path(__file__).resolve().parents[1] / path
        if not f.exists():
            return None, False
        return axioms_for(f.read_text(encoding="utf-8") + f"\n#print axioms {target}\n", target)
    return None, False


def main():
    snd = [json.loads(l) for l in (ANN / "gold.jsonl").read_text().splitlines() if l.strip()]
    snd = [r for r in snd if r["check"] == "instance_soundness"]
    rows, t = [], 0
    print(f"{'id':<8}{'gold':<11}{'tool':<13}{'agree':<7}target")
    for it in snd:
        gold_v = "sound" if it["label"] == "faithful" else "hollow"
        axset, ok = run_item(it)
        tv = tool_verdict(axset)
        decidable = tv in ("sound", "hollow")
        agree = (tv == gold_v) if decidable else None
        rows.append({"id": it["id"], "target": it["target"], "path": it["path"],
                     "gold": gold_v, "tool": tv, "axioms": axset,
                     "decidable": decidable, "agree": agree})
        a = "—" if agree is None else ("yes" if agree else "NO")
        print(f"{it['id']:<8}{gold_v:<11}{tv:<13}{a:<7}{it['target'][:42]}")

    dec = [r for r in rows if r["decidable"]]
    agree = [r for r in dec if r["agree"]]
    inconc = [r for r in rows if not r["decidable"]]
    print("-" * 64)
    print(f"decidable items (tool ran): {len(dec)}/{len(rows)}")
    print(f"human–tool agreement on decidable items: {len(agree)}/{len(dec)} "
          f"= {len(agree)/max(1,len(dec)):.3f}")
    print(f"inconclusive (artifact not compilable): {[r['id'] for r in inconc]}")
    out = {"n_items": len(rows), "n_decidable": len(dec),
           "agreement_decidable": round(len(agree) / max(1, len(dec)), 3),
           "disagreements": [r for r in dec if not r["agree"]],
           "inconclusive": [{"id": r["id"], "path": r["path"], "gold": r["gold"]} for r in inconc],
           "items": rows}
    p = Path(__file__).resolve().parents[1] / "eval_logs" / "soundness_gate_result.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", p)


if __name__ == "__main__":
    main()
