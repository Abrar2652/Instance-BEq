#!/usr/bin/env python3
"""Minimal OpenAI-compatible chat-completions server backed by a local HF model.

Dependency-free (Python stdlib http.server only) so it runs in any venv with (torch 2.4 +
transformers 4.41) with NO extra installs. Implements just enough of the OpenAI API for SITA's
`OpenAI` client and Instance-BEq's `harness/llm.py`:
    GET  /v1/models
    POST /v1/chat/completions   (messages, temperature, max_tokens, n, stop)

Run:
    CUDA_VISIBLE_DEVICES=0 HF_HOME=$HOME/.cache/huggingface \
    python scripts/serve_qwen.py --model Qwen/Qwen2.5-7B-Instruct --port 8765

Then set Code/data/api/config.json -> {"api_key":"local","base_url":"http://127.0.0.1:8765/v1"}
Generation is serialized by a lock (single model, one GPU) — fine for our call volume.
"""
from __future__ import annotations
import argparse, json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = None
TOK = None
SERVED_NAME = "local-model"
GEN_LOCK = threading.Lock()


def load(model_id: str):
    global MODEL, TOK, SERVED_NAME
    t0 = time.time()
    TOK = AutoTokenizer.from_pretrained(model_id)
    MODEL = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.bfloat16, device_map="cuda:0")
    MODEL.eval()
    SERVED_NAME = model_id.split("/")[-1].lower()
    print(f"[serve] loaded {model_id} as '{SERVED_NAME}' in {time.time()-t0:.1f}s "
          f"on {next(MODEL.parameters()).device}", flush=True)


@torch.inference_mode()
def generate(messages, temperature: float, max_tokens: int, n: int, stop):
    ids = TOK.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to("cuda:0")
    prompt_len = ids.shape[1]
    do_sample = temperature and temperature > 0
    texts, completion_toks = [], 0
    with GEN_LOCK:
        for _ in range(max(1, n)):
            out = MODEL.generate(
                ids, max_new_tokens=max_tokens,
                do_sample=do_sample,
                temperature=(temperature if do_sample else None),
                top_p=(0.95 if do_sample else None),
                pad_token_id=TOK.eos_token_id,
            )
            gen = out[0][prompt_len:]
            completion_toks += int(gen.shape[0])
            txt = TOK.decode(gen, skip_special_tokens=True)
            if stop:
                for s in ([stop] if isinstance(stop, str) else stop):
                    if s and s in txt:
                        txt = txt[: txt.index(s)]
            texts.append(txt)
    return texts, prompt_len, completion_toks


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/v1/models"):
            self._send(200, {"object": "list", "data": [{"id": SERVED_NAME, "object": "model"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/v1/chat/completions"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            messages = req.get("messages", [])
            temperature = float(req.get("temperature", 0.7))
            max_tokens = int(req.get("max_tokens") or 4096)  # full Lean files need headroom
            nchoices = int(req.get("n", 1))
            stop = req.get("stop")
            texts, p_len, c_tok = generate(messages, temperature, max_tokens, nchoices, stop)
            self._send(200, {
                "id": "chatcmpl-" + uuid.uuid4().hex[:24],
                "object": "chat.completion",
                "model": req.get("model", SERVED_NAME),
                "choices": [
                    {"index": i, "message": {"role": "assistant", "content": t},
                     "finish_reason": "stop"} for i, t in enumerate(texts)
                ],
                "usage": {"prompt_tokens": p_len, "completion_tokens": c_tok,
                          "total_tokens": p_len + c_tok},
            })
        except Exception as e:
            self._send(500, {"error": {"message": repr(e), "type": "internal"}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    load(args.model)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[serve] OpenAI-compatible endpoint on http://{args.host}:{args.port}/v1", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
