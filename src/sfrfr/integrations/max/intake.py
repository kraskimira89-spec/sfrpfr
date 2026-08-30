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
    "• прислать файлы прямо сюда в этот чат MAX или открыть кабинет на сайте;\n"
    "• позвать специалиста в этот же чат.\n\n"
    "Документы можно прислать прямо сюда в этот чат MAX (PDF/JPG/PNG) — примем, "
    "специалист увидит. Предпочтительно также загрузите в личный кабинет на сайте — "
    "так защищённее (после согласия).\n\n"
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
    "В этом чате MAX — подсказки, связь и вложения: документы можно прислать "
    "прямо сюда. Предпочтительно также — личный кабинет на сайте; "
    "если файл уже здесь — примем, специалист увидит."
)

SUMMARY_TEXT = (
    "Поняли. Для начала нужно загрузить доступные документы и сверить их с данными ИЛС. "
    "Файлы можно прислать прямо сюда в этот чат MAX. "
    "Предпочтительно также — личный кабинет на сайте: там файлы передаются защищённо "
    "(после согласия на обработку данных), это займёт 2–3 минуты. "
    f"Кабинет клиента — только на сайте. {POSITION_SHORT}"
)

DOCS_INFO_TEXT = (
    "Какие документы нужны (кроме выписки ИЛС) — по шагам.\n\n"
    "Главный документ — выписка ИЛС с Госуслуг (паспорт и СНИЛС — база). "
    "Дальше обычно так:\n\n"
    "1) Трудовая история — скан бумажной трудовой книжки "
    "или выписка из электронной трудовой на Госуслугах "
    "(подойдут и договор с книжкой, если так удобнее).\n"
    "2) Если пенсия уже назначена — справка о размере пенсии, "
    "справка о выплатах СФР за период (часто за 12 месяцев / за год) "
    "и/или о назначенных выплатах, плюс банковская выписка за 12 месяцев "
    "по счёту, куда приходит пенсия: чтобы сравнить начисленную "
    "и получаемую пенсию (что начислили СФР и что пришло на счёт).\n"
    "3) Если в ИЛС периоды «не сходятся» с реальной работой — "
    "архивные справки, приказы, трудовые договоры только по спорным местам.\n"
    "4) Особые периоды — военный билет; дети (число детей / свидетельства); "
    "опекунство; льготный/северный/вредный стаж; смена фамилии "
    "(кнопка «Дети, опека, справки»).\n\n"
    "Файлы можно прислать прямо сюда в этот чат MAX (PDF/JPG/PNG) — примем, "
    "специалист увидит. Предпочтительно также загрузите в личный кабинет на сайте — "
    "так защищённее (после согласия). Подробности — кнопками ниже.\n\n"
    f"{POSITION_SHORT}"
)

DOCS_BASE_TEXT = (
    "Базовый набор:\n"
    "• паспорт РФ;\n"
    "• СНИЛС (карточка или электронное уведомление);\n"
    "• выписка из лицевого счёта в СФР (ИЛС) — стаж, взносы, ИПК, "
    "сведения о назначенной пенсии (если уже назначена).\n\n"
    "Если данные в госсистемах полные, для оформления пенсии часто хватает паспорта и СНИЛС. "
    "Для проверки стажа сервисом всё равно нужна свежая выписка ИЛС."
)

DOCS_STAZH_TEXT = (
    "Кроме ИЛС — подтверждение стажа, если периоды в выписке неполные:\n"
    "• скан бумажной трудовой книжки или выписка из электронной трудовой;\n"
    "• электронная копия / договор и книжка — если бумажная под рукой не полностью;\n"
    "• архивные справки с мест работы;\n"
    "• приказы о приёме/увольнении, трудовые договоры;\n"
    "• ведомости зарплаты, лицевые счета;\n"
    "• приказы о переводах, документы о переименовании организации.\n\n"
    "Собирайте подтверждения только по конкретным пробелам после сверки с ИЛС. "
    "Файлы можно прислать прямо сюда в этот чат MAX."
)

DOCS_SPECIAL_TEXT = (
    "Особые периоды и доп. документы:\n"
    "• военный билет — служба в армии;\n"
    "• количество детей / свидетельства о рождении (уход до 1,5 лет); "
    "при утрате — повторное свидетельство или справка о регистрации рождения / ЕГР ЗАГС "
    "(универсальной «справки формы №4 о количестве детей» для всех случаев нет);\n"
    "• опекунство / попечительство — решение или постановление органа опеки; "
    "плюс документы по основанию ухода (если ведёте дело за подопечного);\n"
    "• свидетельство о браке — смена фамилии;\n"
    "• документы об образовании — при необходимости;\n"
    "• льготный стаж (северный, вредный/«горячий», педагогический и т.п.) — "
    "СОУТ, архивные приказы, справки о характере работ, списки профессий "
    "только по спорным периодам.\n\n"
    "Если пенсия уже назначена — сверка выплат:\n"
    "• «Справка о выплатах СФР» / «за период» (часто за 12 месяцев / за год);\n"
    "• «Справка о размере пенсии» или о назначенных выплатах "
    "(или блок о пенсии внутри выписки ИЛС);\n"
    "• банковская выписка по счёту пенсии за 12 месяцев — "
    "сравнить начисленную и получаемую пенсию "
    "(что начислили СФР и что пришло на счёт);\n"
    "• сведения об ИПК — внутри выписки ИЛС.\n\n"
    "Файлы можно прислать прямо сюда в этот чат MAX."
)

DOCS_GOSUSLUGI_TEXT = (
    "Как заказать на Госуслугах (названия услуг):\n\n"
    "1. Войдите в подтверждённую учётную запись на gosuslugi.ru.\n"
    "2. «Выписка из лицевого счета в СФР» "
    "(также: «Извещение о состоянии лицевого счета в СФР») — "
    "раздел «Пенсия» или поиск «ИЛС». Сохраните файл и дату формирования.\n"
    "3. При необходимости — «Выписка из электронной трудовой книжки».\n"
    "4. Если пенсия назначена — «Справка о выплатах СФР» "
    "(период, часто за 12 месяцев / за год) "
    "и/или «Справка о размере пенсии» / о назначенных выплатах; "
    "рядом — банковская выписка за 12 месяцев по счёту пенсии "
    "(из банка / интернет-банка, не с Госуслуг) — "
    "сравнить начисленную и получаемую пенсию.\n"
    "5. «Назначение пенсии» — отдельная услуга, когда наступит право.\n\n"
    "Названия на портале могут чуть меняться — сверяйте на дату заказа.\n"
    "Готовые файлы можно прислать прямо сюда в этот чат MAX; "
    "предпочтительно также — в личный кабинет на сайте."
)

DOCS_MISSING_TEXT = (
    "Если документов нет:\n\n"
    "• Нет Госуслуг — зарегистрируйтесь и подтвердите УЗ в МФЦ / Почтой России / УКЭП.\n"
    "• Нет трудовой — «Выписка из электронной трудовой» на Госуслугах или дубликат "
    "через работодателя/архив.\n"
    "• Нет паспорта — сервис восстановления документов на Госуслугах.\n"
    "• Нет бумажного СНИЛС — номер в ЛК Госуслуг; бумага через СФР/МФЦ.\n"
    "• Ликвидированное предприятие — сначала получите выписку ИЛС; "
    "если у вас не получается — напишите нам, поможем по шагам; "
    "при пробеле — госархив → справки → СФР.\n"
    "• Нет документов о детях/браке — ЗАГС или «Жизненная ситуация» на Госуслугах.\n\n"
    "Подробные шаги по ИЛС — кнопка «Как получить ИЛС»."
)

ILS_HOWTO_TEXT = (
    "Выписка ИЛС — главный документ для проверки стажа и ИПК.\n\n"
    "На Госуслугах услуга называется:\n"
    "«Выписка из лицевого счета в СФР» "
    "(встречается также: «Извещение о состоянии лицевого счета в СФР»).\n\n"
    "1. Войдите в подтверждённую учётную запись "
    "(для близкого — только его логин или по правилам портала).\n"
    "2. «Услуги» → «Пенсия» → «Выписка из лицевого счета в СФР» "
    "(или поиск «ИЛС», «СЗИ-ИЛС»).\n"
    "3. Получите выписку — файл обычно появляется в ЛК в течение дня.\n"
    "4. Сохраните PDF и дату формирования. В выписке также смотрите ИПК "
    "и блок о назначенной пенсии (если пенсия уже есть).\n\n"
    "Если онлайн недоступен — МФЦ или способы на сайте СФР.\n"
    "Если у вас не получается — напишите нам, поможем получить выписку по шагам.\n"
    "Файл можно прислать прямо сюда в этот чат MAX; "
    "предпочтительно также загрузите в личный кабинет на сайте.\n\n"
    f"{POSITION_SHORT}"
)

ILS_HOWTO_MFC_TEXT = (
    "Если Госуслуги недоступны:\n\n"
    "1. Зарегистрируйтесь на gosuslugi.ru (паспорт + СНИЛС).\n"
    "2. Подтвердите учётную запись: МФЦ («Мои документы»), "
    "Почта России или электронная подпись / УКЭП.\n"
    "3. После подтверждения закажите «Выписку из лицевого счета в СФР».\n\n"
    "Без Госуслуг выписку также можно получить в клиентской службе СФР или МФЦ по паспорту.\n\n"
    "Когда выписка будет — нажмите «Уже получил(а) — дальше». "
    "Файл можно прислать прямо сюда в этот чат MAX; "
    "предпочтительно также — в личный кабинет на сайте."
)

EMP_HOWTO_TEXT = (
    "Если бумажной трудовой нет под рукой:\n\n"
    "1. На Госуслугах закажите «Выписку из электронной трудовой книжки» "
    "(раздел «Справки и выписки»).\n"
    "2. Либо подготовьте сканы бумажной трудовой, когда она будет.\n"
    "3. Если книжку утратил работодатель — дубликат оформляет он; "
    "если утратили вы — кадры / архивы бывших работодателей / госархив.\n\n"
    "Даже без полного комплекта можно продолжить: пришлите то, что есть, "
    "прямо сюда в этот чат MAX или в личный кабинет на сайте. "
    "Остальное подскажем по шагам.\n\n"
    f"{POSITION_SHORT}"
)

DOCS_CHECKLIST_URL = "https://proverkastaza.ru/blog/kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr/"
GOSUSLUGI_URL = "https://www.gosuslugi.ru/"
ILS_BLOG_URL = "https://proverkastaza.ru/blog/kak-zakazat-vypisku-ils/"

OPERATOR_CONFIRM_TEXT = f"Передали запрос специалисту. Ответим в этом чате. {POSITION_SHORT}"

# Канон: вложение в чате принимаем; предпочтительно также кабинет на сайте.
UPLOAD_ACCEPTED_TEXT = (
    "Файл приняли — специалист увидит вложение.\n\n"
    "Документы можно присылать прямо сюда в этот чат MAX. "
    "Предпочтительно также загружайте в личный кабинет на сайте — "
    "так защищённее (после согласия на обработку данных).\n\n"
    f"{POSITION_SHORT}"
)
# Устар. имя: раньше был жёсткий отказ.
UPLOAD_BLOCKED_TEXT = UPLOAD_ACCEPTED_TEXT

# Кабинет клиента — только сайт (cabinet.proverkastaza.ru). Mini-app не кабинет.
OPEN_CABINET_LABEL = "Кабинет на сайте"
OPEN_CABINET_WEB_LABEL = OPEN_CABINET_LABEL  # совместимость импортов
OPEN_CABINET_MAX_LABEL = OPEN_CABINET_LABEL  # устар.: раньше «В MAX — кабинет»
CALL_OPERATOR_LABEL = "Позвать специалиста"
DOCS_INFO_LABEL = "Какие документы пригодятся"
DOCS_BASE_LABEL = "Базовый набор"
DOCS_STAZH_LABEL = "Подтверждение стажа"
DOCS_SPECIAL_LABEL = "Дети, опека, справки"
DOCS_GOS_LABEL = "Заказ на Госуслугах"
DOCS_MISSING_LABEL = "Если документов нет"
DOCS_ARTICLE_LABEL = "Чек-лист на сайте"
RESTART_LABEL = "Начать заново"
BACK_LABEL = "Назад"
ILS_GOT_LABEL = "Уже получил(а) — дальше"
ILS_MFC_LABEL = "Нет доступа к Госуслугам"
ILS_ARTICLE_LABEL = "Подробная инструкция"
OPEN_GOSUSLUGI_LABEL = "Открыть Госуслуги"
EMP_CONTINUE_LABEL = "Продолжить без полного комплекта"

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
    ils_howto_done: bool = False
    emp_howto_done: bool = False
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
            if self.ils_available in {"need", "no", "unknown"} and not self.ils_howto_done:
                return "ils_howto"
            if self.employment_records_available is None and self.goal != "sfr_question":
                return "employment"
            if (
                self.employment_records_available == "no"
                and not self.emp_howto_done
                and self.goal != "sfr_question"
            ):
                return "emp_howto"
            if self.device_preference is None:
                return "device"
            return "summary"
        if self.pension_status is None:
            return "pension"
        if self.problem_type is None:
            return "problem"
        if self.ils_available is None:
            return "ils"
        if self.ils_available in {"need", "no", "unknown"} and not self.ils_howto_done:
            return "ils_howto"
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


def ils_howto_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "link", "text": OPEN_GOSUSLUGI_LABEL, "url": GOSUSLUGI_URL}],
            [{"type": "link", "text": ILS_ARTICLE_LABEL, "url": ILS_BLOG_URL}],
            [{"type": "callback", "text": ILS_GOT_LABEL, "payload": "intake:ils_guide:done"}],
            [{"type": "callback", "text": ILS_MFC_LABEL, "payload": "intake:ils_guide:mfc"}],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
            [{"type": "callback", "text": BACK_LABEL, "payload": "intake:back"}],
        ]
    )


def emp_howto_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [{"type": "link", "text": OPEN_GOSUSLUGI_LABEL, "url": GOSUSLUGI_URL}],
            [
                {
                    "type": "callback",
                    "text": EMP_CONTINUE_LABEL,
                    "payload": "intake:emp_guide:done",
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
    # payload intake:device:max|web|help сохранены (совместимость FSM); кабинет — всегда сайт.
    rows: list[list[dict[str, Any]]] = [
        [{"type": "callback", "text": "С телефона", "payload": "intake:device:max"}],
        [
            {
                "type": "callback",
                "text": "С компьютера",
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
    *,
    device: DevicePref | None,
    cabinet_url: str,
    cabinet_max_url: str | None = None,
    cabinet_web_url: str | None = None,
) -> list[dict[str, Any]]:
    """Одна CTA в веб-кабинет. Устар. cabinet_max_url/cabinet_web_url — для совместимости."""
    url = (cabinet_url or cabinet_web_url or cabinet_max_url or "").strip()
    rows: list[list[dict[str, Any]]] = []
    if device == "help":
        rows.append(
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}]
        )
    if url:
        rows.append([{"type": "link", "text": OPEN_CABINET_LABEL, "url": url}])
    rows.extend(
        [
            [{"type": "callback", "text": DOCS_INFO_LABEL, "payload": "intake:docs_info"}],
            [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
            [{"type": "callback", "text": RESTART_LABEL, "payload": "intake:restart"}],
        ]
    )
    return inline_buttons_keyboard(rows)


def upload_blocked_keyboard(
    *,
    cabinet_url: str | None = None,
    cabinet_max_url: str | None = None,
    cabinet_web_url: str | None = None,
) -> list[dict[str, Any]]:
    url = (cabinet_url or cabinet_web_url or cabinet_max_url or "").strip()
    rows: list[list[dict[str, Any]]] = []
    if url:
        rows.append([{"type": "link", "text": OPEN_CABINET_LABEL, "url": url}])
    rows.append(
        [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}]
    )
    return inline_buttons_keyboard(rows)


def docs_info_keyboard(
    *,
    cabinet_url: str | None = None,
    cabinet_max_url: str | None = None,
    cabinet_web_url: str | None = None,
) -> list[dict[str, Any]]:
    url = (cabinet_url or cabinet_web_url or cabinet_max_url or "").strip() or None
    rows: list[list[dict[str, Any]]] = [
        [{"type": "callback", "text": DOCS_BASE_LABEL, "payload": "intake:docs:base"}],
        [{"type": "callback", "text": DOCS_STAZH_LABEL, "payload": "intake:docs:stazh"}],
        [{"type": "callback", "text": DOCS_SPECIAL_LABEL, "payload": "intake:docs:special"}],
        [{"type": "callback", "text": DOCS_GOS_LABEL, "payload": "intake:docs:gosuslugi"}],
        [{"type": "callback", "text": DOCS_MISSING_LABEL, "payload": "intake:docs:missing"}],
        [{"type": "link", "text": OPEN_GOSUSLUGI_LABEL, "url": GOSUSLUGI_URL}],
        [{"type": "link", "text": DOCS_ARTICLE_LABEL, "url": DOCS_CHECKLIST_URL}],
        [{"type": "callback", "text": "Как получить ИЛС", "payload": "intake:docs:ils_howto"}],
        [{"type": "callback", "text": CALL_OPERATOR_LABEL, "payload": "intake:operator"}],
    ]
    if url:
        rows.insert(
            -1,
            [{"type": "link", "text": OPEN_CABINET_LABEL, "url": url}],
        )
    return inline_buttons_keyboard(rows)


def docs_section_keyboard() -> list[dict[str, Any]]:
    """Кнопки после любого раздела перечня документов."""
    return inline_buttons_keyboard(
        [
            [{"type": "callback", "text": "К списку разделов", "payload": "intake:docs_info"}],
            [{"type": "callback", "text": DOCS_GOS_LABEL, "payload": "intake:docs:gosuslugi"}],
            [{"type": "link", "text": OPEN_GOSUSLUGI_LABEL, "url": GOSUSLUGI_URL}],
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
    return "Как вам удобнее открыть кабинет на сайте — с телефона или с компьютера?"


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
    elif step == "ils_howto":
        hint = "Откройте инструкцию кнопками ниже или нажмите «Уже получил(а) — дальше»."
        keyboard = ils_howto_keyboard()
    elif step == "employment":
        hint = employment_question()
        keyboard = employment_keyboard()
    elif step == "emp_howto":
        hint = "Можно открыть Госуслуги или продолжить без полного комплекта."
        keyboard = emp_howto_keyboard()
    elif step == "device":
        hint = device_question()
        keyboard = device_keyboard()
    elif step == "summary":
        hint = "Можно открыть кабинет на сайте или позвать специалиста."
        case_id = intake.case_id if intake else None
        cabinet_url = cabinet_url_for_case(case_id)
        device = intake.device_preference if intake else None
        keyboard = summary_keyboard(device=device, cabinet_url=cabinet_url)
    else:
        hint = "Для кого проверка — за себя или хотите помочь близкому?"
        keyboard = whom_keyboard()
    text = f"{FALLBACK_MENU_TEXT}\n\n{hint}"
    return text, keyboard


def cabinet_url_for_case(case_id: str | None) -> str:
    """Канонический URL веб-кабинета (единственный клиентский кабинет)."""
    settings = get_settings()
    web = settings.cabinet_public_url.rstrip("/")
    if case_id:
        return f"{web}/?{urlencode({'case': case_id})}"
    return web


def cabinet_urls_for_case(case_id: str | None) -> tuple[str, str]:
    """Совместимость: оба значения — веб-кабинет (кабинет в MAX снят)."""
    url = cabinet_url_for_case(case_id)
    return url, url


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
