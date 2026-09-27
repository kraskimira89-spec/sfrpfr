"""Слова «личном кабинете» в ответах бота MAX — ссылка на документы дела в кабинете."""

from __future__ import annotations

import html

CABINET_PHRASE = "личном кабинете"


def linkify_cabinet(text: str, url: str | None) -> tuple[str, str | None]:
    """Вернуть (текст, формат). HTML — чтобы подчёркивания в других ссылках не ломали разметку."""
    target = (url or "").strip()
    if not target or CABINET_PHRASE not in (text or ""):
        return text, None
    escaped = html.escape(text, quote=False)
    link = f'<a href="{html.escape(target)}">{CABINET_PHRASE}</a>'
    return escaped.replace(CABINET_PHRASE, link, 1), "html"
