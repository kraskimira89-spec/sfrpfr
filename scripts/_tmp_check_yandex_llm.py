from __future__ import annotations

import traceback
from pathlib import Path

from sfrfr.ai.llm import LLMClient
from sfrfr.core.config import get_settings


def main() -> None:
    get_settings.cache_clear()
    s = get_settings()
    print("ai_provider", s.ai_provider)
    print("folder_set", bool(s.yandex_folder_id), "folder_len", len(s.yandex_folder_id or ""))
    print("key_set", bool(s.yandex_api_key), "key_len", len(s.yandex_api_key or ""))
    print("model", s.yandex_model)
    print("base_url", s.yandex_base_url)

    client = LLMClient()
    print("available", client.available)
    print("resolved_model", client.model)

    if not client.available:
        print("FAIL: LLMClient.available is False")
        return

    try:
        text = client.chat(
            system="Ответь одной короткой фразой на русском.",
            user="Скажи только: ключ Яндекса работает",
            temperature=0.0,
        )
        print("chat_ok", repr(text[:200]))
    except Exception:
        print("chat_error")
        traceback.print_exc()


if __name__ == "__main__":
    main()
