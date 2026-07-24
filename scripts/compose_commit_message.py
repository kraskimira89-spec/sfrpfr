#!/usr/bin/env python3
"""Сформировать понятное сообщение git-коммита на русском по staged-изменениям.

Формат:
  заголовок (1 строка)
  <пустая строка>
  тело: что изменилось и зачем (2–6 коротких пунктов)

1) Если доступен LLM проекта (Yandex/OpenAI) — просит ИИ.
2) Иначе — развёрнутая эвристика по путям/diff.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MAX_DIFF_CHARS = 10000
MAX_SUBJECT = 100
MAX_BODY_LINES = 8


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
    return _git("diff", "--cached", "-U2", "--no-color")


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
    if re.search(r"hooks?\.json|workflow|\.github/|auto_commit|compose_commit", joined):
        return "chore"
    return "feat"


def _kind_title(kind: str) -> str:
    return {
        "feat": "Новое",
        "fix": "Исправление",
        "docs": "Документация",
        "test": "Тесты",
        "refactor": "Рефакторинг",
        "chore": "Служебное",
    }.get(kind, "Обновление")


def _areas(names: list[str]) -> list[str]:
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
        ("supabase/", "Supabase"),
    )
    lower_names = [n.replace("\\", "/") for n in names]
    for prefix, label in mapping:
        if any(n.startswith(prefix) or f"/{prefix}" in n for n in lower_names):
            if label not in areas:
                areas.append(label)
    return areas or ["проект"]


def _iter_added_lines(patch: str, *, skip_files: set[str] | None = None) -> list[str]:
    """Только строки '+' из diff, с опциональным исключением файлов."""
    skip = {p.replace("\\", "/") for p in (skip_files or set())}
    current: str | None = None
    added: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            # diff --git a/path b/path
            parts = line.split()
            current = parts[-1][2:] if len(parts) >= 4 else None
            continue
        if current and current.replace("\\", "/") in skip:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return added


def _change_hints(patch: str, names: list[str] | None = None) -> list[str]:
    """Грубые подсказки из добавленных строк diff (не из всего файла)."""
    skip = {"scripts/compose_commit_message.py"}
    lowered = "\n".join(_iter_added_lines(patch, skip_files=skip)).lower()
    if not lowered.strip():
        return []

    hints: list[str] = []
    checks = (
        (r"emailredirectto|письм[оа] отправлено|signInWithOtp|verifyOtp", "вход / OTP / письмо авторизации"),
        (r"site_url|emailRedirectTo|redirect_to", "редиректы / URL авторизации"),
        (r"recaptcha|grecaptcha", "проверка reCAPTCHA"),
        (r"calendar\.google|CalendarClient|calendar_id", "календарь"),
        (r"drive\.google|DriveClient|folder_id", "Google Drive / папки"),
        (r"\bruff\b|E501|UP017", "линт / стиль кода"),
        (r"deploy-vps|workflow_dispatch|github/workflows", "деплой / CI"),
        (r"compose_commit_message|auto_commit_push|AUTO_COMMIT_MSG", "автосообщения коммитов"),
        (r"smtp_|mailer_|noreply@", "почта / SMTP"),
        (r"supabase\.co|createClient\(", "Supabase Auth"),
        (r"hooks\.json|followup_message|stop-hook", "хуки Cursor"),
    )
    for pattern, label in checks:
        if re.search(pattern, lowered) and label not in hints:
            hints.append(label)
        if len(hints) >= 4:
            break
    # если правили только генератор сообщений
    if names and all(n.replace("\\", "/").endswith("compose_commit_message.py") for n in names):
        return ["автосообщения коммитов"]
    return hints


def _format_message(subject: str, body_lines: list[str]) -> str:
    subject = _clean_subject(subject)
    body: list[str] = []
    for raw in body_lines:
        line = raw.strip()
        if not line:
            continue
        line = line.lstrip("-•* ").strip()
        if not line:
            continue
        body.append(f"- {line}")
        if len(body) >= MAX_BODY_LINES:
            break
    if not body:
        return subject
    return subject + "\n\n" + "\n".join(body)


def _clean_subject(text: str) -> str:
    text = text.strip().strip('"').strip("'")
    text = re.sub(r"\s+", " ", text)
    text = text.replace("AUTO:", "").strip()
    # убрать markdown-обёртки
    text = re.sub(r"^#+\s*", "", text)
    if len(text) > MAX_SUBJECT:
        text = text[: MAX_SUBJECT - 1].rstrip() + "…"
    return text


def _normalize_llm_message(raw: str) -> str | None:
    text = raw.strip().strip("`")
    if not text:
        return None
    # убрать возможные префиксы вроде «Сообщение:»
    text = re.sub(r"^(сообщение коммита|commit message)\s*:\s*", "", text, flags=re.I)
    lines = [ln.rstrip() for ln in text.splitlines()]
    # отбросить пустые в начале
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return None

    subject = _clean_subject(lines[0])
    rest = lines[1:]
    # пропустить одну пустую после заголовка
    if rest and not rest[0].strip():
        rest = rest[1:]

    body_lines: list[str] = []
    for ln in rest:
        s = ln.strip()
        if not s:
            continue
        if s.lower() in {"```", "```text", "```markdown"}:
            continue
        body_lines.append(s)

    if not body_lines:
        # модель вернула одну строку — развернём минимально
        return subject
    return _format_message(subject, body_lines)


def _heuristic(names: list[str], stat: str, patch: str) -> str:
    kind = _guess_kind(names, patch)
    areas = _areas(names)
    area = ", ".join(areas[:3])
    title = _kind_title(kind)
    hints = _change_hints(patch, names)

    if len(names) == 1:
        subject = f"{title}: правки в «{area}» ({Path(names[0]).name})"
    else:
        subject = f"{title}: правки в «{area}» ({len(names)} файлов)"

    body: list[str] = [
        f"Затронуты области: {area}.",
    ]
    if hints:
        body.append("По содержанию изменений: " + "; ".join(hints) + ".")
    else:
        body.append("Обновлены рабочие файлы проекта по текущей задаче агента.")

    show = names[:6]
    listed = ", ".join(Path(n).name for n in show)
    if len(names) > 6:
        listed += f" и ещё {len(names) - 6}"
    body.append(f"Файлы: {listed}.")

    # краткая сводка из --stat
    summary = next(
        (ln.strip() for ln in reversed(stat.splitlines()) if "changed" in ln or "файл" in ln),
        "",
    )
    if summary:
        body.append(f"Сводка diff: {summary}.")

    body.append("Цель: зафиксировать результат шага работы, чтобы CI/деплой подхватил актуальный код.")
    return _format_message(subject, body)


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
    areas = ", ".join(_areas(names))
    clipped = patch[:MAX_DIFF_CHARS]
    system = (
        "Ты пишешь сообщения git commit на русском для команды разработки.\n"
        "Ответ — ТОЛЬКО текст коммита, без кавычек и без markdown-оград.\n\n"
        "Структура строго такая:\n"
        "1) Первая строка — заголовок до 100 символов: понятно «что сделали».\n"
        "2) Пустая строка.\n"
        "3) Тело из 3–6 пунктов, каждый с новой строки, начинай с «- ».\n"
        "В теле объясни: что изменилось, зачем это нужно пользователю/системе, "
        "на что обратить внимание (риски, деплой, конфиг).\n"
        "Пиши простым языком, без воды и без шаблонов AUTO/agent stop/timestamp.\n"
        "Не копируй весь diff — суммируй смысл."
    )
    user = (
        f"Тип изменений (подсказка): {kind} ({_kind_title(kind)})\n"
        f"Области: {areas}\n"
        f"Файлы ({len(names)}):\n"
        + "\n".join(f"- {n}" for n in names[:50])
        + "\n\n"
        f"stat:\n{stat[:2000]}\n\n"
        f"diff (усечённый):\n{clipped}"
    )
    try:
        raw = client.chat(system=system, user=user, temperature=0.3)
    except Exception:
        return None
    return _normalize_llm_message(raw or "")


def _emit(msg: str, out_path: Path | None) -> None:
    text = msg.rstrip() + "\n"
    if out_path is not None:
        out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


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
        _emit(
            _format_message(
                "Служебное: синхронизация изменений",
                [
                    f"Не удалось прочитать staged-diff (код {exc.returncode}).",
                    "Коммит создан как технический снимок текущего состояния.",
                ],
            ),
            out_path,
        )
        return 0
    if not names:
        _emit(
            _format_message(
                "Служебное: нет staged-изменений",
                ["Индекс пуст — коммитить нечего."],
            ),
            out_path,
        )
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


if __name__ == "__main__":
    raise SystemExit(main())
