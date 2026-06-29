"""LLM client: the single point through which Instance-BEq calls a language model.

Real mode mirrors SITA's `first_generation.call_deepseek_api` (OpenAI-compatible DeepSeek
endpoint, config from `Code/data/api/config.json`). Mock mode returns canned responses keyed by a
prompt tag. Responses are cached on disk by (prompt, model, temperature) so re-runs are free.

All LLM access goes through here so mock mode can intercept it (a repo guardrail).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional

from instance_beq.config import InstanceBEqConfig, DEFAULT


def _hash(prompt: str, model: str, temp: float) -> str:
    return hashlib.sha256(f"{model}|{temp}|{prompt}".encode("utf-8")).hexdigest()


class LLMClient:
    def __init__(self, cfg: InstanceBEqConfig = DEFAULT, mock_db: dict | None = None):
        self.cfg = cfg
        self.mock = cfg.mock
        self._mock_db = mock_db or {}
        self._client = None
        self._cache_dir = cfg.llm_cache_dir
        if self._cache_dir:
            Path(self._cache_dir).mkdir(parents=True, exist_ok=True)

    # ---- mock plumbing -----------------------------------------------------
    @staticmethod
    def _tag(prompt: str) -> str:
        m = re.search(r"@mock:(\S+)", prompt)
        if m:
            return m.group(1)
        return "h:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    def _mock_lookup(self, prompt: str) -> str:
        key = self._tag(prompt)
        if key not in self._mock_db:
            raise KeyError(
                f"Mock LLM has no fixture for key {key!r}. Add it to tests/mock_data/llm_db.json "
                f"or embed `@mock:<key>` in the prompt."
            )
        return self._mock_db[key]

    # ---- caching -----------------------------------------------------------
    def _cache_path(self, prompt: str) -> Optional[Path]:
        if not self._cache_dir:
            return None
        return Path(self._cache_dir) / (_hash(prompt, self.cfg.model_name, self.cfg.temperature) + ".json")

    # ---- real client -------------------------------------------------------
    def _ensure_client(self):
        if self._client is not None:
            return
        from openai import OpenAI  # imported lazily so mock mode needs no openai install
        ext = json.loads(Path(self.cfg.api_config_path).read_text(encoding="utf-8"))
        self._client = OpenAI(api_key=ext["api_key"], base_url=ext["base_url"])

    # ---- public API --------------------------------------------------------
    def complete(self, prompt: str) -> str:
        if self.mock:
            return self._mock_lookup(prompt)
        cache = self._cache_path(prompt)
        if cache and cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))["response"]
        self._ensure_client()
        for attempt in range(3):
            try:
                resp = self._client.chat.completions.create(
                    model=self.cfg.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                    temperature=self.cfg.temperature,
                )
                text = resp.choices[0].message.content or ""
                if cache:
                    cache.write_text(json.dumps({"prompt": prompt, "response": text}),
                                     encoding="utf-8")
                return text
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return ""

    @staticmethod
    def extract_lean(raw: str) -> str:
        """Mirror SITA first_generation.extract_lean_code."""
        raw = raw.strip()
        if raw.startswith("```lean4"):
            raw = raw[8:].lstrip()
        elif raw.startswith("```lean"):
            raw = raw[7:].lstrip()
        if raw.endswith("```"):
            raw = raw[:-3]
        return raw.strip()
