"""Диагностика в личном чате MAX (ТЗ-20 + marketing §10.1): модель, store, тексты и клавиатуры."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

from sfrfr.core.config import get_settings
from sfrfr.core.copy import POSITION_SHORT
from sfrfr.integrations.max.client import inline_buttons_keyboard

# Legacy goal (для совместимости store / метрик)
Goal = Literal["check_experience", "missing_period", "sfr_question", "operator"]
ForWhom = Literal["self", "relative"]
PensionStatus = Literal["before", "assigned"]
ProblemType = Literal["ils_stazh", "north", "documents", "sfr_refusal"]
IlsAvail = Literal["yes", "no", "unknown", "need"]
EmpAvail = Literal["yes", "partial", "no"]
DevicePref = Literal["max", "web", "help"]
IntakeStatus = Literal["started", "completed", "handed_to_operator", "abandoned"]

PROBLEM_TO_GOAL: dict[str, Goal] = {
    "ils_stazh": "check_experience",
    "north": "check_experience",
    "documents": "missing_period",
    "sfr_refusal": "sfr_question",
}

GOAL_LABELS: dict[str, str] = {
    "check_experience": "Проверить стаж",
    "missing_period": "Не хватает периода работы",
    "sfr_question": "Есть отказ или вопрос СФР",
    "operator": "Спросить специалиста",
}

WELCOME_TEXT = (
    "Здравствуйте!\n\n"
    "Я бот сервиса «Проверка стажа». Здесь можно:\n"
    "• коротко уточнить ситуацию — за себя или хотите помочь близкому;\n"
    "• понять, какие документы нужны для сверки стажа и ИЛС;\n"
    "• перейти в личный кабинет и безопасно загрузить файлы;\n"
    "• позвать специалиста в этот же чат.\n\n"
    "Сканы и трудовую книжку в сообщения не присылайте — только через кабинет.\n\n"
    "Мы проверим Ваши документы, сделаем проекты обращений и план подачи — "
    "расскажем всё по шагам, но подаёте через СФР или Госуслуги вы сами. "
    "Решение принимает СФР.\n\n"
    "Для кого проверка? Выберите кнопку ниже."
)


def format_welcome_text(*, display_name: str | None = None) -> str:
    """Приветствие с именем, если оно известно и выглядит как имя человека."""
    name = (display_name or "").strip()
    if not name or name.lower().startswith("max ") or "@" in name:
        return WELCOME_TEXT
    # Только первое слово / короткое обращение — без длинных ФИО из формы
    first = name.split()[0]
    if len(first) < 2 or len(first) > 40 or not first[0].isalpha():
        return WELCOME_TEXT
    return WELCOME_TEXT.replace("Здравствуйте!", f"Здравствуйте, {first}!", 1)


FALLBACK_MENU_TEXT = (
    "Спасибо за сообщение.\n\n"
    "Сейчас удобнее отвечать кнопками ниже — так мы быстрее поймём ситуацию. "
    "Если хотите поговорить с человеком, нажмите «Позвать специалиста».\n\n"
    "Сканы и трудовую книжку присылайте только через личный кабинет."
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

OPEN_CABINET_MAX_LABEL = "В MAX — кабинет"
OPEN_CABINET_WEB_LABEL = "В браузере — кабинет"
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
    for_whom: ForWhom | None = None
    pension_status: PensionStatus | None = None
    problem_type: ProblemType | None = None
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
        """Текущий шаг FSM для метрик (marketing §10.1)."""
        if self.goal == "operator":
            return "summary"
        if self.for_whom is None and self.goal is None:
            return "whom"
        # Legacy: goal set without for_whom — continue old path
        if self.goal is not None and self.for_whom is None:
            if self.ils_available is None:
                return "ils"
            if self.employment_records_available is None and self.goal != "sfr_question":
                return "employment"
            if self.device_preference is None:
                return "device"
            return "summary"
        if self.pension_status is None:
            return "pension"
        if self.problem_type is None:
            return "problem"
        if self.ils_available is None:
            return "ils"
        if self.device_preference is None:
            return "device"
        return "summary"

    def sync_goal_from_problem(self) -> None:
        if self.problem_type and self.problem_type in PROBLEM_TO_GOAL:
            self.goal = PROBLEM_TO_GOAL[self.problem_type]


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
        loaded: dict[str, MaxIntakeRecord] = {}
        for mid, data in rows.items():
            if not isinstance(data, dict):
                continue
            # Игнор неизвестных ключей при эволюции схемы
            known = {f.name for f in fields(MaxIntakeRecord)}
            filtered = {k: v for k, v in data.items() if k in known}
            try:
                loaded[mid] = MaxIntakeRecord(**filtered)
            except TypeError:
                continue
        self._rows = loaded

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


def whom_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "За себя", "payload": "intake:whom:self"}],
            [{"type": "callback", "text": "Помогаю близкому", "payload": "intake:whom:relative"}],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
        ]
    )


def pension_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "До пенсии", "payload": "intake:pension:before"}],
            [
                {
                    "type": "callback",
                    "text": "Пенсия назначена",
                    "payload": "intake:pension:assigned",
                }
            ],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
            [{"type": "callback", "text": BACK_LABEL, "payload": "intake:back"}],
        ]
    )


def problem_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "ИЛС и стаж", "payload": "intake:problem:ils_stazh"}],
            [
                {
                    "type": "callback",
                    "text": "Северный или льготный",
                    "payload": "intake:problem:north",
                }
            ],
            [{"type": "callback", "text": "Документы", "payload": "intake:problem:documents"}],
            [{"type": "callback", "text": "Отказ СФР", "payload": "intake:problem:sfr_refusal"}],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
            [{"type": "callback", "text": BACK_LABEL, "payload": "intake:back"}],
        ]
    )


def goal_keyboard() -> list[dict[str, Any]]:
    """Стартовое меню = шаг «для кого» (§10.1)."""
    return whom_keyboard()


def ils_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "Есть выписка ИЛС", "payload": "intake:ils:yes"}],
            [{"type": "callback", "text": "Нужно получить", "payload": "intake:ils:need"}],
            [{"type": "callback", "text": "Нет", "payload": "intake:ils:no"}],
            [
                {
                    "type": "callback",
                    "text": "Не знаю, как получить",
                    "payload": "intake:ils:unknown",
                }
            ],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
            [{"type": "callback", "text": BACK_LABEL, "payload": "intake:back"}],
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


def whom_question(*, display_name: str | None = None) -> str:
    return format_welcome_text(display_name=display_name)


def pension_question() -> str:
    return "Пенсия уже назначена или ещё до пенсии?"


def problem_question() -> str:
    return "Что сейчас важнее всего?"


def ils_question() -> str:
    return "Есть выписка из индивидуального лицевого счёта (ИЛС)?"


def employment_question() -> str:
    return "Есть трудовая книжка или справки о работе?"


def device_question() -> str:
    return "Как вам удобнее загрузить документы?"


def free_text_nudge(*, intake: MaxIntakeRecord | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Ответ на произвольный текст без LLM: короткая подсказка + кнопки текущего шага."""
    step = intake.step() if intake is not None else "whom"
    if step == "pension":
        hint = pension_question()
        keyboard = pension_keyboard()
    elif step == "problem":
        hint = problem_question()
        keyboard = problem_keyboard()
    elif step == "ils":
        hint = ils_question()
        keyboard = ils_keyboard()
    elif step == "employment":
        hint = employment_question()
        keyboard = employment_keyboard()
    elif step == "device":
        hint = device_question()
        keyboard = device_keyboard()
    elif step == "summary":
        hint = "Можно открыть кабинет или позвать специалиста."
        case_id = intake.case_id if intake else None
        max_url, web_url = cabinet_urls_for_case(case_id)
        device = intake.device_preference if intake else None
        keyboard = summary_keyboard(
            device=device, cabinet_max_url=max_url, cabinet_web_url=web_url
        )
    else:
        hint = "Для кого проверка — за себя или хотите помочь близкому?"
        keyboard = whom_keyboard()
    text = f"{FALLBACK_MENU_TEXT}\n\n{hint}"
    return text, keyboard


def cabinet_urls_for_case(case_id: str | None) -> tuple[str, str]:
    settings = get_settings()
    web = settings.cabinet_public_url.rstrip("/")
    max_app = (settings.max_miniapp_url or web).rstrip("/")
    if case_id:
        q = urlencode({"case": case_id})
        return f"{max_app}?{q}", f"{web}/?{q}"
    return max_app, web


def problem_type_for_goal(goal: Goal | None) -> str:
    if not goal:
        return "intake"
    mapping = {
        "check_experience": "check_experience",
        "missing_period": "missing_period",
        "sfr_question": "sfr_question",
        "operator": "operator",
    }
    return mapping.get(goal, "intake")
