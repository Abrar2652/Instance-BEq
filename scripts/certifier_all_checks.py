#!/usr/bin/env python3
"""Instance-BEq certifier verdicts on ALL FOUR checks, per gold item (fills the gap where only
soundness was scored). Verdicts:
  * instance_soundness  -> the decidable #print axioms gate (exact).            [soundness_gate_result.json]
  * definitional        -> prove  D_gen = D_ref  where D_ref is an INDEPENDENT reference: the LLM
                           sees only the informal spec + the def SIGNATURE (never D_gen's body),
                           returns a body, we splice it and discharge equality by a tactic ensemble.
                           Kernel-sound: a proved equality is genuine (precision 1); else abstain.
  * transfer_validity   -> re-synthesize / compile the apply-based specialization proof.
  * statement_faithful. -> the LLM bridge (check 3b); reuse the LLM-judge verdict, reported as such.
Out: eval_logs/certifier_all_checks_result.json
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instance_beq.config import InstanceBEqConfig, SORRY_TOKENS
from instance_beq.harness.lean_oracle import LeanOracle
from openai import OpenAI

cfg = InstanceBEqConfig(mock=False)
oracle = LeanOracle(cfg)
ext = json.loads(Path(cfg.api_config_path).read_text())
client = OpenAI(api_key=ext["api_key"], base_url=ext["base_url"])
MODEL = "qwen2.5-7b-instruct"
ANN = Path(__file__).resolve().parents[1] / "instance_beq/annotation"
LOG = Path(__file__).resolve().parents[1] / "eval_logs"

DEF_TACS = ["rfl", "unfold {t}; rfl", "unfold {t} {t}_ref; ext x; ring_nf; simp",
            "unfold {t} {t}_ref; funext x; ring", "simp only [{t}, {t}_ref]"]


def llm(prompt, max_tokens=220):
    r = client.chat.completions.create(model=MODEL, temperature=0.0, max_tokens=max_tokens,
                                       messages=[{"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip()


def extract_def_sig(src, target):
    """Return (sig_text) for `def <target> <sig> := <body>` — signature only, no body."""
    m = re.search(rf"\bdef\s+{re.escape(target)}\b(.*?):=", src, re.DOTALL)
    return m.group(1).strip() if m else None


def strip_fence(s):
    s = re.sub(r"^```[a-z0-9]*\n?", "", s.strip())
    return re.sub(r"\n?```$", "", s).strip()


def cert_definitional(it):
    src, target = it["lean_source"], it["target"]
    sig = extract_def_sig(src, target)
    if sig is None:
        return "unknown", "no def signature found"
    prompt = (f"Write ONLY the Lean 4 body (right of `:=`) for a definition with this signature, "
              f"encoding the informal objective below. Use the same notations the file uses "
              f"(e.g. ‖·‖₂). Output just the expression, no `def`, no imports, no prose.\n\n"
              f"Signature:  def {target}_ref {sig} :=\n\nInformal objective:\n{str(it['informal'])[:900]}")
    body = strip_fence(llm(prompt))
    if not body or len(body) > 400:
        return "unknown", "no usable reference body"
    for tac in DEF_TACS:
        snippet = (src + f"\n\ndef {target}_ref {sig} := {body}\n"
                   f"example : @{target} = @{target}_ref := by {tac.format(t=target)}\n")
        res = oracle.check_snippet(snippet)
        if res.ok and not res.errors:
            return "faithful", f"proved via [{tac}] vs ref={body[:60]}"
    return "unknown", f"ensemble exhausted (ref={body[:60]})"


def cert_transfer(it):
    """The instantiated theorem's proof is apply-based; it is a valid specialization iff the file
    compiles the target without an `apply`/unify error. Compile the (built) module and check."""
    src, target = it["lean_source"], it["target"]
    res = oracle.check_snippet(src + f"\n#check @{target}\n")
    if res.ok and not res.errors:
        return "valid", "apply-specialization compiles"
    # an apply-unification failure on the target => invalid specialization
    if any("apply" in e.get("message", "") or "unify" in e.get("message", "")
           or "unsolved" in e.get("message", "") for e in res.errors):
        return "invalid", "apply failed to unify"
    return "unknown", f"compile error ({len(res.errors)})"


def main():
    gold = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"gold.jsonl").read_text().splitlines() if l.strip()}
    items = {json.loads(l)["id"]: json.loads(l) for l in (ANN/"pool/items.jsonl").read_text().splitlines() if l.strip()}
    gate = {r["id"]: r for r in json.loads((LOG/"soundness_gate_result.json").read_text())["items"]}
    judge = {r["id"]: r for r in json.loads((LOG/"llm_judge_gold_result.json").read_text())["items"]}

    out, t0 = [], time.time()
    for iid, g in gold.items():
        chk = g["check"]; it = items[iid]
        if chk == "instance_soundness":
            r = gate.get(iid, {})
            v = (None if not r or not r.get("decidable") else ("unfaithful" if r["tool"] == "hollow" else "faithful"))
            mech = "gate(#print axioms)"
        elif chk == "definitional":
            res, why = cert_definitional(it); v = "faithful" if res == "faithful" else None; mech = "defeq(ref)"
        elif chk == "transfer_validity":
            res, why = cert_transfer(it); v = "faithful" if res == "valid" else ("unfaithful" if res == "invalid" else None); mech = "apply"
        else:  # statement_faithfulness -> LLM bridge (3b)
            v = judge.get(iid, {}).get("llm_judge"); mech = "3b/LLM-bridge"
        out.append({"id": iid, "check": chk, "gold": g["label"], "certifier": v, "mech": mech})
        print(f"  {iid} {chk[:5]:<5} gold={g['label']:<11} cert={str(v):<11} [{mech}]", flush=True)

    (LOG/"certifier_all_checks_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    # quick integrity: certifier must never false-certify a gold-unfaithful as faithful on formal checks
    fc = [r for r in out if r["check"] in ("definitional", "instance_soundness", "transfer_validity")
          and r["gold"] == "unfaithful" and r["certifier"] == "faithful"]
    print(f"\nfalse certifications on formal checks (must be 0): {len(fc)}  [{time.time()-t0:.0f}s]")
    print("wrote", LOG/"certifier_all_checks_result.json")


if __name__ == "__main__":
    main()
