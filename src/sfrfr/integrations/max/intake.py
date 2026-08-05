"""Диагностика в личном чате MAX (ТЗ-20): модель, store, тексты и клавиатуры."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

from sfrfr.core.config import get_settings
from sfrfr.core.copy import POSITION_SHORT
from sfrfr.integrations.max.client import inline_buttons_keyboard

Goal = Literal["check_experience", "missing_period", "sfr_question", "operator"]
IlsAvail = Literal["yes", "no", "unknown"]
EmpAvail = Literal["yes", "partial", "no"]
DevicePref = Literal["max", "web", "help"]
IntakeStatus = Literal["started", "completed", "handed_to_operator", "abandoned"]

GOAL_LABELS: dict[str, str] = {
    "check_experience": "Проверить стаж",
    "missing_period": "Не хватает периода работы",
    "sfr_question": "Есть отказ или вопрос СФР",
    "operator": "Спросить специалиста",
}

WELCOME_TEXT = (
    "Здравствуйте! Поможем разобраться со стажем и документами. "
    f"{POSITION_SHORT} С чего начнём?"
)

SUMMARY_TEXT = (
    "Поняли. Для начала нужно загрузить доступные документы и сверить их с данными ИЛС. "
    "В личном кабинете документы передаются защищённо. Это займёт 2–3 минуты. "
    f"Перед загрузкой потребуется согласие на обработку данных. {POSITION_SHORT}"
)

DOCS_INFO_TEXT = (
    "Обычно нужны: выписка из индивидуального лицевого счёта (ИЛС) и трудовая книжка "
    "или справки о работе. Точный список подскажем после загрузки. "
    f"Документы принимаются только в личном кабинете, не в этом чате. {POSITION_SHORT}"
)

OPERATOR_CONFIRM_TEXT = f"Передали запрос специалисту. Ответим в этом чате. {POSITION_SHORT}"

UPLOAD_BLOCKED_TEXT = (
    "Документы через сообщения MAX не принимаются. "
    "В личном кабинете они передаются защищённо — после согласия на обработку данных. "
    f"{POSITION_SHORT}"
)

OPEN_CABINET_MAX_LABEL = "Открыть личный кабинет для документов"
OPEN_CABINET_WEB_LABEL = "Открыть личный кабинет в браузере"
CALL_OPERATOR_LABEL = "Позвать специалиста"
DOCS_INFO_LABEL = "Какие документы пригодятся"
RESTART_LABEL = "Начать заново"
BACK_LABEL = "Назад"

CALLBACK_PREFIX = "intake:"


@dataclass
class MaxIntakeRecord:
    id: str
    max_user_id: str
    goal: Goal | None = None
    ils_available: IlsAvail | None = None
    employment_records_available: EmpAvail | None = None
    device_preference: DevicePref | None = None
    status: IntakeStatus = "started"
    client_id: str | None = None
    case_id: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def step(self) -> str:
        """Текущий шаг FSM для метрик."""
        if self.goal is None:
            return "goal"
        if self.ils_available is None and self.goal != "operator":
            return "ils"
        if self.employment_records_available is None and self.goal not in {
            "operator",
            "sfr_question",
        }:
            return "employment"
        if self.device_preference is None and self.goal != "operator":
            return "device"
        return "summary"


def default_intake_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "max_intake.json"


class MaxIntakeStore:
    """Файловое хранилище диагностики (локально / тесты; prod может зеркалить в Postgres)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_intake_path()
        self._lock = threading.RLock()
        self._rows: dict[str, MaxIntakeRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._rows = {}
            return
        raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        rows = raw.get("rows") or {}
        self._rows = {
            mid: MaxIntakeRecord(**data) for mid, data in rows.items() if isinstance(data, dict)
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rows": {mid: asdict(rec) for mid, rec in self._rows.items()}}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_active(self, max_user_id: str) -> MaxIntakeRecord | None:
        with self._lock:
            rec = self._rows.get(str(max_user_id))
            if rec is None:
                return None
            if rec.status in {"started", "completed", "handed_to_operator"}:
                return rec
            return None

    def upsert_started(self, max_user_id: str) -> MaxIntakeRecord:
        """Повторный /start не стирает незавершённую диагностику."""
        with self._lock:
            mid = str(max_user_id)
            existing = self._rows.get(mid)
            if existing is not None and existing.status == "started":
                existing.updated_at = datetime.now(UTC).isoformat()
                self._save()
                return existing
            rec = MaxIntakeRecord(id=str(uuid.uuid4()), max_user_id=mid, status="started")
            self._rows[mid] = rec
            self._save()
            return rec

    def restart(self, max_user_id: str) -> MaxIntakeRecord:
        with self._lock:
            mid = str(max_user_id)
            old = self._rows.get(mid)
            if old is not None:
                old.status = "abandoned"
                old.updated_at = datetime.now(UTC).isoformat()
            rec = MaxIntakeRecord(id=str(uuid.uuid4()), max_user_id=mid, status="started")
            self._rows[mid] = rec
            self._save()
            return rec

    def save(self, rec: MaxIntakeRecord) -> MaxIntakeRecord:
        with self._lock:
            rec.updated_at = datetime.now(UTC).isoformat()
            self._rows[str(rec.max_user_id)] = rec
            self._save()
            return rec


_store: MaxIntakeStore | None = None
_store_lock = threading.Lock()


def get_intake_store(path: Path | None = None) -> MaxIntakeStore:
    global _store
    with _store_lock:
        if path is not None:
            _store = MaxIntakeStore(path)
            return _store
        if _store is None:
            _store = MaxIntakeStore()
        return _store


def reset_intake_store(path: Path | None = None) -> MaxIntakeStore:
    global _store
    with _store_lock:
        _store = MaxIntakeStore(path or default_intake_path())
        return _store


def goal_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": GOAL_LABELS["check_experience"],
                    "payload": "intake:goal:check_experience",
                }
            ],
            [
                {
                    "type": "callback",
                    "text": GOAL_LABELS["missing_period"],
                    "payload": "intake:goal:missing_period",
                }
            ],
            [
                {
                    "type": "callback",
                    "text": GOAL_LABELS["sfr_question"],
                    "payload": "intake:goal:sfr_question",
                }
            ],
            [
                {
                    "type": "callback",
                    "text": GOAL_LABELS["operator"],
                    "payload": "intake:goal:operator",
                }
            ],
        ]
    )


def ils_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "Да", "payload": "intake:ils:yes"}],
            [{"type": "callback", "text": "Нет", "payload": "intake:ils:no"}],
            [
                {
                    "type": "callback",
                    "text": "Не знаю, как получить",
                    "payload": "intake:ils:unknown",
                }
            ],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
        ]
    )


def employment_keyboard(*, with_back: bool = True) -> list[dict[str, Any]]:
    rows: list[list[dict[str, Any]]] = [
        [{"type": "callback", "text": "Да", "payload": "intake:emp:yes"}],
        [{"type": "callback", "text": "Часть документов", "payload": "intake:emp:partial"}],
        [{"type": "callback", "text": "Нет", "payload": "intake:emp:no"}],
        [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
    ]
    if with_back:
        rows.append([{"type": "callback", "text": BACK_LABEL, "payload": "intake:back"}])
    return inline_buttons_keyboard(rows)


def device_keyboard(*, with_back: bool = True) -> list[dict[str, Any]]:
    rows: list[list[dict[str, Any]]] = [
        [{"type": "callback", "text": "С телефона в MAX", "payload": "intake:device:max"}],
        [
            {
                "type": "callback",
                "text": "С компьютера в браузере",
                "payload": "intake:device:web",
            }
        ],
        [{"type": "callback", "text": "Нужна помощь", "payload": "intake:device:help"}],
        [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
    ]
    if with_back:
        rows.append([{"type": "callback", "text": BACK_LABEL, "payload": "intake:back"}])
    return inline_buttons_keyboard(rows)


def summary_keyboard(
    *, device: DevicePref | None, cabinet_max_url: str, cabinet_web_url: str
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, Any]]] = []
    if device == "web":
        rows.append([{"type": "link", "text": OPEN_CABINET_WEB_LABEL, "url": cabinet_web_url}])
        rows.append([{"type": "link", "text": OPEN_CABINET_MAX_LABEL, "url": cabinet_max_url}])
    elif device == "help":
        rows.append(
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}]
        )
        rows.append([{"type": "link", "text": OPEN_CABINET_MAX_LABEL, "url": cabinet_max_url}])
        rows.append([{"type": "link", "text": OPEN_CABINET_WEB_LABEL, "url": cabinet_web_url}])
    else:
        rows.append([{"type": "link", "text": OPEN_CABINET_MAX_LABEL, "url": cabinet_max_url}])
        rows.append([{"type": "link", "text": OPEN_CABINET_WEB_LABEL, "url": cabinet_web_url}])
    rows.extend(
        [
            [{"type": "callback", "text": DOCS_INFO_LABEL, "payload": "intake:docs_info"}],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
            [{"type": "callback", "text": RESTART_LABEL, "payload": "intake:restart"}],
        ]
    )
    return inline_buttons_keyboard(rows)


def upload_blocked_keyboard(*, cabinet_max_url: str, cabinet_web_url: str) -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "link", "text": OPEN_CABINET_MAX_LABEL, "url": cabinet_max_url}],
            [{"type": "link", "text": OPEN_CABINET_WEB_LABEL, "url": cabinet_web_url}],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
        ]
    )


def ils_question() -> str:
    return "Есть выписка из индивидуального лицевого счёта (ИЛС)?"


def employment_question() -> str:
    return "Есть трудовая книжка или справки о работе?"


def device_question() -> str:
    return "Как вам удобнее загрузить документы?"


def cabinet_urls_for_case(case_id: str) -> tuple[str, str]:
    settings = get_settings()
    mini = (settings.max_miniapp_url or settings.max_public_bot_url or "").rstrip("/")
    if mini and "case=" not in mini:
        sep = "&" if "?" in mini else "?"
        mini_url = f"{mini}{sep}{urlencode({'case': case_id})}"
    else:
        mini_url = mini or settings.max_chat_url
    web = f"{settings.cabinet_public_url.rstrip('/')}/cases/{case_id}"
    return mini_url, web


def problem_type_for_goal(goal: Goal | None) -> str:
    mapping = {
        "check_experience": "check_experience",
        "missing_period": "missing_period",
        "sfr_question": "sfr_question",
        "operator": "operator_request",
    }
    return mapping.get(goal or "", "client_open")
