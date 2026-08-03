# -*- coding: utf-8 -*-
import json
import urllib.request
from pathlib import Path

raw = Path("secrets/deepseek.env").read_text(encoding="utf-8")
key = ""
for line in raw.splitlines():
    line = line.strip()
    if line.startswith("DEEPSEEK_API_KEY="):
        key = line.split("=", 1)[1].strip().strip('"').strip("'")
print("key_prefix", key[:6], "len", len(key))
body = json.dumps(
    {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Ответь одним словом: ок"}],
        "max_tokens": 16,
        "temperature": 0,
    }
).encode()
req = urllib.request.Request(
    "https://api.deepseek.com/chat/completions",
    data=body,
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        print("status", resp.status)
        print("model", data.get("model"))
        print("content", (data.get("choices") or [{}])[0].get("message", {}).get("content"))
except Exception as e:
    if hasattr(e, "read"):
        print("HTTP_ERR", getattr(e, "code", None), e.read().decode("utf-8", "replace")[:500])
    else:
        print("ERR", type(e).__name__, e)
