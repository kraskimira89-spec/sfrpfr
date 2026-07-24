#!/usr/bin/env python3
"""Сформировать короткое сообщение git-коммита на русском по staged-изменениям.

1) Если доступен LLM проекта (Yandex/OpenAI) — просит ИИ.
2) Иначе — эвристика по путям файлов.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MAX_DIFF_CHARS = 6000
MAX_SUBJECT = 90


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()


def _staged_names() -> list[str]:
    out = _git("diff", "--cached", "--name-only")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _staged_stat() -> str:
    return _git("diff", "--cached", "--stat")


def _staged_patch() -> str:
    return _git("diff", "--cached", "-U1", "--no-color")


def _guess_kind(names: list[str], patch: str) -> str:
    joined = " ".join(names).lower() + "\n" + patch[:2000].lower()
    if re.search(r"\btest[s]?/|test_|\.spec\.", joined):
        if re.search(r"fix|bug|ошиб|lint|ruff|ci", joined):
            return "fix"
        return "test"
    if re.search(r"docs/|\.md$", joined) and not re.search(
        r"src/|apps/|scripts/", joined
    ):
        return "docs"
    if re.search(r"fix|bug|ошиб|hotfix|lint|ruff|ci|deploy|unblock", joined):
        return "fix"
    if re.search(r"refactor|переимен|очист", joined):
        return "refactor"
    if re.search(r"hooks?\.json|workflow|\.github/|auto_commit", joined):
        return "chore"
    return "feat"


def _area(names: list[str]) -> str:
    areas: list[str] = []
    mapping = (
        ("apps/cabinet", "кабинет клиента"),
        ("apps/admin", "админ-кабинет"),
        ("src/sfrfr/integrations/calendar", "Google Calendar"),
        ("src/sfrfr/integrations/drive", "Google Drive"),
        ("src/sfrfr/integrations/recaptcha", "reCAPTCHA"),
        ("src/sfrfr/integrations", "интеграции"),
        ("src/sfrfr/api", "API"),
        ("src/sfrfr", "бэкенд"),
        ("scripts/", "скрипты"),
        (".cursor/", "хуки Cursor"),
        (".github/", "CI/CD"),
        ("docs/", "документация"),
        ("tests/", "тесты"),
        ("web/", "веб"),
    )
    lower_names = [n.replace("\\", "/") for n in names]
    for prefix, label in mapping:
        if any(n.startswith(prefix) or f"/{prefix}" in n for n in lower_names):
            if label not in areas:
                areas.append(label)
    if not areas:
        return "проект"
    return ", ".join(areas[:2])


def _heuristic(names: list[str], stat: str, patch: str) -> str:
    kind = _guess_kind(names, patch)
    area = _area(names)
    labels = {
        "feat": "добавить",
        "fix": "исправить",
        "docs": "обновить документацию",
        "test": "обновить тесты",
        "refactor": "рефакторинг",
        "chore": "служебные правки",
    }
    verb = labels.get(kind, "обновить")
    file_hint = Path(names[0]).name if names else "файлы"
    extra = ""
    if len(names) == 1:
        extra = f" ({file_hint})"
    elif len(names) <= 3:
        extra = " (" + ", ".join(Path(n).name for n in names) + ")"
    else:
        extra = f" ({len(names)} файлов)"
    subject = f"{verb}: {area}{extra}"
    # чуть контекста из stat первой строки
    first_stat = next((ln.strip() for ln in stat.splitlines() if "|" in ln), "")
    if first_stat and len(subject) < 50:
        subject = f"{verb}: {area} — {file_hint}"
    return _clean(subject)


def _clean(text: str) -> str:
    text = text.strip().strip('"').strip("'")
    text = re.sub(r"\s+", " ", text)
    text = text.replace("AUTO:", "").strip()
    if len(text) > MAX_SUBJECT:
        text = text[: MAX_SUBJECT - 1].rstrip() + "…"
    # первая буква строчная после типа? оставляем как есть
    return text


def _llm_message(names: list[str], stat: str, patch: str) -> str | None:
    try:
        sys.path.insert(0, str(REPO / "src"))
        from sfrfr.ai.llm import LLMClient  # noqa: WPS433
    except Exception:
        return None

    try:
        client = LLMClient()
    except Exception:
        return None
    if not client.available:
        return None

    kind = _guess_kind(names, patch)
    area = _area(names)
    clipped = patch[:MAX_DIFF_CHARS]
    system = (
        "Ты помощник для git commit. Ответь ОДНОЙ строкой на русском — "
        "готовым сообщением коммита. Без кавычек, без markdown, без пояснений. "
        "Формат: «глагол: краткое описание». Фокус на зачем/что изменилось. "
        "Не используй AUTO, timestamp и английские шаблоны agent stop."
    )
    user = (
        f"Предполагаемый тип: {kind}\n"
        f"Область: {area}\n"
        f"Файлы:\n" + "\n".join(f"- {n}" for n in names[:40]) + "\n\n"
        f"stat:\n{stat[:1500]}\n\n"
        f"diff (усечённый):\n{clipped}"
    )
    try:
        raw = client.chat(system=system, user=user, temperature=0.2)
    except Exception:
        return None
    if not raw or not raw.strip():
        return None
    # взять первую непустую строку
    line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    return _clean(line) if line else None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    out_path: Path | None = None
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] in {"-o", "--output"}:
        out_path = Path(args[1])

    try:
        names = _staged_names()
    except subprocess.CalledProcessError as exc:
        msg = f"chore: синхронизация изменений ({exc.returncode})"
        _emit(msg, out_path)
        return 0
    if not names:
        _emit("chore: нет staged-изменений", out_path)
        return 0

    stat = ""
    patch = ""
    try:
        stat = _staged_stat()
        patch = _staged_patch()
    except subprocess.CalledProcessError:
        pass

    msg = _llm_message(names, stat, patch)
    if not msg:
        msg = _heuristic(names, stat, patch)
    _emit(msg, out_path)
    return 0


def _emit(msg: str, out_path: Path | None) -> None:
    text = msg.rstrip() + "\n"
    if out_path is not None:
        out_path.write_text(text, encoding="utf-8", newline="\n")
    # для отладки в консоли
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
