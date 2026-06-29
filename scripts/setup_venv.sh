#!/usr/bin/env bash
# Build a dedicated, project-owned venv for Instance-BEq using uv (no ensurepip needed).
# Stack mirrors the proven-good config: torch 2.4 cu121 + transformers 4.41 + openai + ST.
set -o pipefail
export PATH="$HOME/.local/bin:$PATH"
VENV="${VENV:-$(cd "$(dirname "$0")/.." && pwd)/.venv}"
PY="$VENV/bin/python"
ts() { date '+%H:%M:%S'; }

echo "[$(ts)] (re)creating venv at $VENV with uv"
rm -rf "$VENV"
uv venv "$VENV" --python 3.10 2>&1 | tail -3 || exit 1

echo "[$(ts)] === torch 2.4.0 (cu121) ==="
uv pip install --python "$PY" torch==2.4.0 --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -3

echo "[$(ts)] === rest of stack ==="
uv pip install --python "$PY" "numpy<2" "transformers==4.41.2" accelerate openai \
    sentence-transformers tqdm pydantic pandas scipy 2>&1 | tail -3

echo "[$(ts)] === verify ==="
"$PY" - <<'PY'
import torch, transformers, openai, sentence_transformers as st, numpy
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), "ndev", torch.cuda.device_count())
print("transformers", transformers.__version__, "| openai", openai.__version__,
      "| ST", st.__version__, "| numpy", numpy.__version__)
PY
echo "[$(ts)] === DONE ==="
