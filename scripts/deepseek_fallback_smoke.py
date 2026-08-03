# -*- coding: utf-8 -*-
"""Smoke: DeepSeek platform как запасной LLMClient."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# подтянуть secrets/deepseek.env в процесс, не печатая ключ
env_path = ROOT / "secrets" / "deepseek.env"
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from sfrfr.core.config import get_settings  # noqa: E402
from sfrfr.ai.llm import LLMClient  # noqa: E402

get_settings.cache_clear()
client = LLMClient.for_deepseek_fallback(purpose="analyze")
print("provider", client.provider)
print("available", client.available)
print("model", client.model)
print("base", client.base_url)
out = client.chat(system="Ты тестовый ассистент.", user="Ответь одним словом: ок")
print("reply", out[:80])
print("OK" if out else "EMPTY")
