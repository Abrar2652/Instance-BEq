#!/usr/bin/env bash
# Build the Lean/Optlib oracle for Instance-BEq.
# Pinned via lake-manifest.json (Mathlib v4.13.0) -> NO `lake update` (guardrail #1).
# Runnable standalone; logs everything with timestamps.
set -o pipefail
export PATH="$HOME/.elan/bin:$PATH"
LEAN_DIR="${LEAN_DIR:-$(cd "$(dirname "$0")/.." && pwd)/Code/lean}"
ts() { date '+%H:%M:%S'; }
cd "$LEAN_DIR" || { echo "no lean dir"; exit 1; }

echo "[$(ts)] toolchain: $(cat lean-toolchain)"
echo "[$(ts)] elan: $(elan --version 2>&1)"

echo "[$(ts)] === STEP 1: lake exe cache get (Mathlib oleans; triggers toolchain install) ==="
for attempt in 1 2 3; do
  echo "[$(ts)] cache get attempt $attempt"
  if lake exe cache get 2>&1; then echo "[$(ts)] cache get OK"; break; fi
  echo "[$(ts)] cache get attempt $attempt failed; retrying"; sleep 10
done

echo "[$(ts)] === STEP 2: lake build (Optlib) ==="
lake build 2>&1
BUILD_RC=$?
echo "[$(ts)] lake build returncode=$BUILD_RC"

echo "[$(ts)] === STEP 3: validate gold examples compile (the certifier's substrate) ==="
for f in Optlib/Autoformalization/Example/GD_example.lean \
         Optlib/Autoformalization/Example/PGD_example.lean; do
  echo "[$(ts)] --- compiling $f ---"
  lake env lean "$f" 2>&1 | tail -15
  echo "[$(ts)] $f exit=${PIPESTATUS[0]}"
done

echo "[$(ts)] === DONE (build rc=$BUILD_RC) ==="
