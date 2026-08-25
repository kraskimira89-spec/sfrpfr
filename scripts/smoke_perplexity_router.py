#!/usr/bin/env python3
"""Smoke: Perplexity Router API (OpenAI Chat Completions).

Не печатает ключ. Ожидание: HTTP 200 и shape с choices[0].
401 — ключ/auth; 429 — rate limit / overload (Retry-After);
400 — модель не в каталоге ключа; 402 — модель вне tier.

Usage:
  .\\.venv\\Scripts\\Activate.ps1
  $env:PERPLEXITY_API_KEY = "…"   # в своём терминале, не в чат
  python scripts/smoke_perplexity_router.py
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    key = (os.environ.get("PERPLEXITY_API_KEY") or "").strip()
    if not key:
        print(
            "PERPLEXITY_API_KEY не задан. Создайте ключ в "
            "https://console.perplexity.ai и экспортируйте в своём терминале "
            "(не вставляйте ключ в чат). Router API — private preview."
        )
        return 2

    try:
        from openai import OpenAI
    except ImportError:
        print('Нужен пакет openai: pip install -e ".[ai]"')
        return 2

    base = (
        os.environ.get("PERPLEXITY_BASE_URL") or "https://api.perplexity.ai/router/v1"
    ).rstrip("/")
    client = OpenAI(api_key=key, base_url=base)

    # 1) Каталог = allowlist
    try:
        models_resp = client.models.list()
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status_code", None) or getattr(
            getattr(exc, "response", None), "status_code", None
        )
        print(f"GET /models failed status={status} type={type(exc).__name__}")
        return 1

    ids = [str(m.id) for m in (models_resp.data or []) if getattr(m, "id", None)]
    print(f"GET /models ok count={len(ids)} sample={ids[:5]!r}")
    if not ids:
        print("Пустой каталог — нет доступа к Router или ключ без Router.")
        return 1

    model = (os.environ.get("PERPLEXITY_MODEL") or "").strip() or ids[0]
    if model not in ids:
        print(f"PERPLEXITY_MODEL={model!r} нет в каталоге ключа; используем {ids[0]!r}")
        model = ids[0]

    # 2) Минимальный chat.completions
    try:
        raw = client.chat.completions.with_raw_response.create(
            model=model,
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
        )
        status = raw.status_code
        resp = raw.parse()
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status_code", None) or getattr(
            getattr(exc, "response", None), "status_code", None
        )
        print(f"POST /chat/completions failed status={status} type={type(exc).__name__}")
        return 1

    n_choices = len(resp.choices or [])
    has_content = bool(n_choices and (resp.choices[0].message.content or "").strip())
    usage = getattr(resp, "usage", None)
    usage_keys = sorted(usage.model_dump(exclude_none=True).keys()) if usage else []
    print(
        f"POST /chat/completions status={status} model={resp.model!r} "
        f"choices={n_choices} has_content={has_content} usage_keys={usage_keys}"
    )
    return 0 if status == 200 and n_choices == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
