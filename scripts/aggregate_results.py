"""Merge per-task certifier outputs (cert_*.json) into a single summary for metrics."""
from __future__ import annotations
import glob, json, sys
from pathlib import Path

def main(results_dir="instance_beq/eval/results", out=None):
    certs = []
    mock_any = False
    for f in sorted(glob.glob(f"{results_dir}/cert_*.json")):
        s = json.loads(Path(f).read_text(encoding="utf-8"))
        mock_any = mock_any or s.get("mock", False)
        certs += s.get("certificates", [])
    tally = {}
    for c in certs:
        v = c["formal_faithful"]; tally[v] = tally.get(v, 0) + 1
    summary = {"mock": mock_any, "n_files": len(certs),
               "formal_verdicts": tally, "certificates": certs}
    out = out or f"{results_dir}/summary_merged.json"
    Path(out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"merged {len(certs)} certificates -> {out}")
    print(json.dumps(tally, indent=2))

if __name__ == "__main__":
    main(*sys.argv[1:])
