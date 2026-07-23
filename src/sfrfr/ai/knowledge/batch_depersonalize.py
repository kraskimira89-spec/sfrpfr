"""Пакетное обезличивание текстовых файлов в каталоге."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sfrfr.ai.knowledge.importer import read_dialog_text
from sfrfr.ai.pii.depersonalize import depersonalize_text

_TEXT_SUFFIXES = frozenset({".md", ".txt", ".json", ".html", ".htm", ".csv"})
_SKIP_SUFFIXES = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".doc", ".docx"})


@dataclass(frozen=True)
class DepersonalizeResult:
    source: Path
    output: Path | None
    status: str  # ok | skipped | error
    detail: str = ""


def depersonalize_dir(
    inbox: Path,
    out: Path,
    *,
    client_name: str | None = None,
    recursive: bool = True,
) -> list[DepersonalizeResult]:
    """
    Копирует текстовые файлы из inbox в out с заменой ПДн.

    PDF/сканы пропускаются (не кладём в cleaned). Структура каталогов сохраняется.
    """
    inbox = inbox.resolve()
    out = out.resolve()
    if not inbox.is_dir():
        raise NotADirectoryError(inbox)

    out.mkdir(parents=True, exist_ok=True)
    results: list[DepersonalizeResult] = []
    paths = sorted(inbox.rglob("*") if recursive else inbox.iterdir())

    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(inbox)
        suffix = path.suffix.lower()

        if suffix in _SKIP_SUFFIXES or suffix not in _TEXT_SUFFIXES:
            results.append(
                DepersonalizeResult(
                    source=path,
                    output=None,
                    status="skipped",
                    detail=f"unsupported:{suffix or '(noext)'}",
                )
            )
            continue

        dest = out / rel
        try:
            raw = read_dialog_text(path)
            safe = depersonalize_text(raw, client_name=client_name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(safe, encoding="utf-8")
            results.append(
                DepersonalizeResult(source=path, output=dest, status="ok")
            )
        except OSError as exc:
            results.append(
                DepersonalizeResult(
                    source=path,
                    output=None,
                    status="error",
                    detail=str(exc),
                )
            )

    return results
