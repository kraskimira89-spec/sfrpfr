"""Анкета отзыва в MAX: вопросы кнопками → черновик → ссылка на /otzyv/."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sfrfr.core.review_draft import (
    QUESTIONS,
    REVIEW_ANKETA_URL,
    REVIEW_PUBLISH_URL,
    build_review_draft,
)
from sfrfr.integrations.max.client import inline_buttons_keyboard

_STORE_LOCK = threading.Lock()
_DEFAULT_PATH = Path("var") / "max_review_sessions.json"


@dataclass
class ReviewSession:
    user_id: str
    step: str = "helped"  # question id or "done"
    answers: dict[str, str] = field(default_factory=dict)
    draft: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def _store_path() -> Path:
    return _DEFAULT_PATH


def _load() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_session(user_id: str) -> ReviewSession | None:
    with _STORE_LOCK:
        raw = _load().get(str(user_id))
    if not isinstance(raw, dict):
        return None
    return ReviewSession(
        user_id=str(user_id),
        step=str(raw.get("step") or "helped"),
        answers=dict(raw.get("answers") or {}),
        draft=str(raw.get("draft") or ""),
        updated_at=str(raw.get("updated_at") or ""),
    )


def save_session(session: ReviewSession) -> None:
    session.updated_at = datetime.now(UTC).isoformat()
    with _STORE_LOCK:
        data = _load()
        data[str(session.user_id)] = asdict(session)
        _save(data)


def clear_session(user_id: str) -> None:
    with _STORE_LOCK:
        data = _load()
        data.pop(str(user_id), None)
        _save(data)


def _question_by_id(qid: str) -> dict[str, Any] | None:
    for q in QUESTIONS:
        if q["id"] == qid:
            return q
    return None


def start_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "Сформулировать отзыв", "payload": "review:start"}],
            [{"type": "link", "text": "Анкета на сайте", "url": REVIEW_ANKETA_URL}],
            [{"type": "link", "text": "Сразу форма Яндекса", "url": REVIEW_PUBLISH_URL}],
        ]
    )


def question_keyboard(qid: str) -> list[dict[str, Any]] | None:
    q = _question_by_id(qid)
    if not q:
        return None
    rows: list[list[dict[str, Any]]] = []
    row: list[dict[str, Any]] = []
    for oid, label in (q["options"] or {}).items():
        row.append({"type": "callback", "text": label[:64], "payload": f"review:a:{qid}:{oid}"})
        if len(row) >= 1:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"type": "callback", "text": "Отмена", "payload": "review:cancel"}])
    return inline_buttons_keyboard(rows)


def done_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "link", "text": "Публиковать отзыв на Яндексе", "url": REVIEW_PUBLISH_URL}],
            [{"type": "link", "text": "Открыть анкету на сайте", "url": REVIEW_ANKETA_URL}],
            [{"type": "callback", "text": "Заново", "payload": "review:start"}],
        ]
    )


def soft_ask_attachments() -> list[dict[str, Any]]:
    """Кнопки к мягкой просьбе после completed."""
    return start_keyboard()


def format_soft_ask_with_flow() -> str:
    return (
        "Спасибо, что обратились в «Проверку стажа».\n\n"
        "Если захотите и будет удобно — можно оставить короткий отзыв о нашей работе "
        "(необязательно). Можно ответить на 3 вопроса кнопками ниже — мы соберём черновик текста, "
        "а публикуете вы сами на Яндексе.\n\n"
        "Если не хотите — ничего нажимать не нужно. Больше не будем напоминать."
    )


def handle_review_callback(*, user_id: str, payload: str) -> dict[str, Any] | None:
    """
    Обработать callback review:*.
    Возвращает None если не наш payload; иначе {text, attachments}.
    """
    if not payload.startswith("review:"):
        return None

    if payload == "review:cancel":
        clear_session(user_id)
        return {
            "text": "Хорошо, отзыв не нужен. Мы на связи, если понадобится помощь по документам.",
            "attachments": None,
        }

    if payload == "review:start":
        session = ReviewSession(user_id=str(user_id), step="helped", answers={})
        save_session(session)
        q = _question_by_id("helped")
        return {
            "text": f"Отзыв — про нашу работу, не про решение СФР.\n\n{(q or {}).get('label')}",
            "attachments": question_keyboard("helped"),
        }

    if payload.startswith("review:a:"):
        parts = payload.split(":")
        # review:a:{qid}:{oid}
        if len(parts) < 4:
            return {
                "text": "Не понял ответ. Нажмите «Сформулировать отзыв» ещё раз.",
                "attachments": start_keyboard(),
            }
        qid, oid = parts[2], parts[3]
        session = get_session(user_id) or ReviewSession(user_id=str(user_id))
        q = _question_by_id(qid)
        if not q or oid not in (q.get("options") or {}):
            return {"text": "Этот вариант устарел. Начнём снова.", "attachments": start_keyboard()}
        session.answers[qid] = oid

        order = [str(item["id"]) for item in QUESTIONS]
        try:
            idx = order.index(qid)
        except ValueError:
            idx = -1
        if idx >= 0 and idx + 1 < len(order):
            nxt = order[idx + 1]
            session.step = nxt
            save_session(session)
            nq = _question_by_id(nxt)
            return {
                "text": str((nq or {}).get("label") or "Следующий вопрос"),
                "attachments": question_keyboard(nxt),
            }

        # Все вопросы — черновик
        result = build_review_draft(session.answers)
        draft = str(result.get("draft") or "").strip()
        session.draft = draft
        session.step = "done"
        save_session(session)
        text = (
            "Черновик по вашим ответам (можете поправить перед публикацией):\n\n"
            f"«{draft}»\n\n"
            "1) Скопируйте текст.\n"
            "2) Нажмите «Публиковать отзыв на Яндексе» и вставьте его в форму.\n"
            "Оценку звёздами выбираете вы."
        )
        return {"text": text, "attachments": done_keyboard()}

    return {
        "text": "Можно сформулировать отзыв кнопками или открыть анкету на сайте.",
        "attachments": start_keyboard(),
    }


# re-export for notifications
__all__ = [
    "clear_session",
    "done_keyboard",
    "format_soft_ask_with_flow",
    "handle_review_callback",
    "question_keyboard",
    "soft_ask_attachments",
    "start_keyboard",
]
