"""Единый клиентский статус дела для ответов MAX.

Источники — документы/ingest/задача проверки/специалист/E-F, не история чата
как единственное доказательство анализа. При закрытых E/F не пишем
«диагностика идёт».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

StatusKind = Literal[
    "no_docs",
    "receiving",
    "checking",
    "missing",
    "error",
    "kit_ready_no_analysis",
    "result_ready",
    "staff_active",
]

UserIntent = Literal["thanks", "working_question", "clarification", "other"]

_MISSING_RU = {"ils": "выписка о стаже (ИЛС)", "labor": "трудовая книжка"}
_PENDING_INGEST = frozenset(
    {"needs_reupload", "uploading", "security_check", "uploaded", "under_review"}
)
_FAILED_INGEST = frozenset({"blocked_security", "failed"})
_THANKS_RE = re.compile(
    r"^(спасибо|благодарю|спс|ok|ок|хорошо|понял[ао]?|ясно)[.! ]*$",
    re.IGNORECASE,
)
_WORKING_RE = re.compile(
    # стебель «работ» — ловит «работаете»/«работаешь», не только сущ. «работа»
    r"(ещ[её]\s+работ|вы\s+работ|ид[её]т\s+провер|когда\s+будет|сколько\s+ждать|"
    r"статус|что\s+с\s+моим|обработ)",
    re.IGNORECASE,
)
_CLARIFY_RE = re.compile(
    r"(период|работал[аи]?|с\s+\d|по\s+\d|стаж|завод|север|льгот|"
    r"не\s+учли|пропуск|с\s+\d{4})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClientCaseStatus:
    kind: StatusKind
    doc_count: int = 0
    have_buckets: frozenset[str] = field(default_factory=frozenset)
    missing_buckets: tuple[str, ...] = ()
    check_status: str | None = None
    last_error: str | None = None
    result_summary: str | None = None
    staff_active: bool = False
    ef_open: bool = False
    quiet_receiving: bool = False


def classify_user_intent(text: str) -> UserIntent:
    clean = " ".join(str(text or "").strip().split())
    if not clean:
        return "other"
    if _THANKS_RE.match(clean):
        return "thanks"
    if _WORKING_RE.search(clean):
        return "working_question"
    if len(clean) >= 12 and _CLARIFY_RE.search(clean):
        return "clarification"
    return "other"


def resolve(
    *,
    documents: list[dict[str, Any]] | None = None,
    document_check: dict[str, Any] | None = None,
    staff_active: bool = False,
    ef_open: bool | None = None,
    case_quiet: bool = False,
    ingest_pending: bool | None = None,
    result_summary: str | None = None,
    result_current: bool = False,
) -> ClientCaseStatus:
    """Рассчитать статус по фактам дела (без LLM)."""
    from sfrfr.services.diag_offer_gate import ef_stages_open
    from sfrfr.services.max_kit_status import collect_case_doc_buckets

    docs = [d for d in (documents or []) if isinstance(d, dict)]
    ef = bool(ef_stages_open()) if ef_open is None else bool(ef_open)
    if staff_active:
        return ClientCaseStatus(
            kind="staff_active",
            doc_count=len(docs),
            staff_active=True,
            ef_open=ef,
        )

    have = frozenset(collect_case_doc_buckets(docs))
    missing = tuple(code for code in ("ils", "labor") if code not in have)
    pending = (
        bool(ingest_pending)
        if ingest_pending is not None
        else _docs_ingest_pending(docs)
    )
    failed = _docs_ingest_failed(docs)
    check = document_check or {}
    check_status = str(check.get("status") or "").strip().lower() or None
    last_error = str(check.get("last_error") or "").strip() or None
    stale = bool(check.get("stale"))
    check_result = check.get("result") if isinstance(check.get("result"), dict) else None

    if not docs:
        return ClientCaseStatus(kind="no_docs", ef_open=ef)

    result_ready = (
        result_current
        and bool(result_summary)
        and check_status in {"completed", "needs_action"}
        and not stale
        and bool(check_result)
    )
    # Brief/итог уже у клиента важнее quiet «обрабатываем» (thanks / working_question).
    if result_ready:
        return ClientCaseStatus(
            kind="result_ready",
            doc_count=len(docs),
            have_buckets=have,
            check_status=check_status,
            result_summary=result_summary,
            ef_open=ef,
        )

    if case_quiet or pending:
        return ClientCaseStatus(
            kind="receiving",
            doc_count=len(docs),
            have_buckets=have,
            missing_buckets=missing,
            check_status=check_status,
            last_error=last_error,
            quiet_receiving=bool(case_quiet),
            ef_open=ef,
        )

    if check_status in {"queued", "running"}:
        return ClientCaseStatus(
            kind="checking",
            doc_count=len(docs),
            have_buckets=have,
            missing_buckets=missing,
            check_status=check_status,
            last_error=last_error,
            ef_open=ef,
        )

    if check_status == "failed" or failed:
        return ClientCaseStatus(
            kind="error",
            doc_count=len(docs),
            have_buckets=have,
            missing_buckets=missing,
            check_status=check_status or "failed",
            last_error=last_error or "Не удалось обработать часть файлов.",
            ef_open=ef,
        )

    if missing:
        return ClientCaseStatus(
            kind="missing",
            doc_count=len(docs),
            have_buckets=have,
            missing_buckets=missing,
            check_status=check_status,
            ef_open=ef,
        )
    # Полный комплект, но краткая диагностика не запущена / E/F закрыты.
    return ClientCaseStatus(
        kind="kit_ready_no_analysis",
        doc_count=len(docs),
        have_buckets=have,
        check_status=check_status,
        last_error=last_error,
        ef_open=ef,
    )


def resolve_for_case(
    case_id: str | None,
    *,
    staff_active: bool | None = None,
    case_quiet: bool | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> ClientCaseStatus:
    """Загрузить факты по case_id и рассчитать статус."""
    cid = str(case_id or "").strip()
    docs: list[dict[str, Any]] = list(documents or [])
    check: dict[str, Any] | None = None
    quiet = bool(case_quiet) if case_quiet is not None else False

    if cid:
        if not docs:
            try:
                from sfrfr.db.case_repository import CaseRepository

                docs = list(CaseRepository().list_documents(cid) or [])
            except Exception:  # noqa: BLE001
                docs = []
        try:
            from sfrfr.services.staff_document_check import get_case_document_check

            check = get_case_document_check(cid)
        except Exception:  # noqa: BLE001
            check = None
        try:
            from sfrfr.services.case_chat_context import (
                fetch_recent_case_messages,
                staff_dialog_active,
            )

            history = fetch_recent_case_messages(cid)
            if staff_active is None:
                staff_active = staff_dialog_active(history)
        except Exception:  # noqa: BLE001
            if staff_active is None:
                staff_active = False
        if case_quiet is None:
            try:
                from sfrfr.integrations.max.document_background import is_case_quiet

                quiet = is_case_quiet(cid)
            except Exception:  # noqa: BLE001
                quiet = False

    result_summary = None
    result_current = False
    if isinstance(check, dict):
        result = check.get("result") if isinstance(check.get("result"), dict) else None
        if result and not check.get("stale"):
            result_summary = str(
                check.get("status_label")
                or result.get("next_action")
                or "Проверка комплекта завершена."
            )
            result_current = str(check.get("status") or "").lower() in {
                "completed",
                "needs_action",
            }

    if not result_current:
        brief_summary, brief_current = _brief_summary_for_case(cid, docs=docs)
        if brief_current and brief_summary:
            result_summary = brief_summary
            result_current = True
            if not isinstance(check, dict):
                check = {
                    "status": "completed",
                    "stale": False,
                    "result": {"next_action": brief_summary},
                }
            else:
                check = {
                    **check,
                    "status": check.get("status") or "completed",
                    "stale": False,
                    "result": check.get("result")
                    if isinstance(check.get("result"), dict)
                    else {"next_action": brief_summary},
                }

    return resolve(
        documents=docs,
        document_check=check,
        staff_active=bool(staff_active),
        case_quiet=quiet,
        result_summary=result_summary,
        result_current=result_current,
    )


def reply_text(
    status: ClientCaseStatus,
    *,
    intent: UserIntent = "other",
) -> str:
    """Клиентский текст по таблице владельца + intent."""
    base = _base_reply(status)
    if intent == "thanks":
        return f"Пожалуйста. {base}"
    if intent == "clarification":
        return f"Спасибо, пояснение сохранили к делу. {base}"
    if intent == "working_question":
        kit_complete = (
            "ils" in status.have_buckets
            and "labor" in status.have_buckets
            and not status.missing_buckets
        )
        # Quiet/receiving при полном комплекте — не шаблон «обрабатываем»
        # (после brief soft-ask / «Вы ещё работаете?»).
        # SFRFR-83: текст строго по check_status (queued ≠ running ≠ «не запущена»).
        if status.kind == "receiving" and kit_complete:
            return _kit_check_status_reply(
                check_status=status.check_status,
                last_error=status.last_error,
            )
        if status.kind in {"receiving", "checking", "error"}:
            return base
        if status.kind == "kit_ready_no_analysis":
            return _kit_check_status_reply(
                check_status=status.check_status or None,
                last_error=status.last_error,
            )
    return base


def _kit_check_status_reply(
    *,
    check_status: str | None,
    last_error: str | None = None,
) -> str:
    """Честный текст по staff docs-check при полном комплекте.

    Без безусловного «результат придёт в этот чат» — автодоставка не
    гарантирована (нужен staff / brief / доставка).
    """
    check = str(check_status or "").strip().lower()
    tail = "Повторно присылать те же файлы не нужно."
    if not check:
        return f"Документы в деле. Проверка ещё не запущена. {tail}"
    if check == "queued":
        return f"Документы в деле. Проверка ожидает запуска. {tail}"
    if check == "running":
        return f"Документы в деле. Проверка выполняется. {tail}"
    if check == "failed":
        detail = (last_error or "задержка при обработке").strip()
        return (
            f"Документы в деле. По проверке возникла задержка: {detail}. "
            f"Специалист разберётся и напишет сюда. {tail}"
        )
    if check == "completed":
        return (
            f"Документы в деле. Проверка комплекта уже выполнена. "
            f"Если итог не виден — напишите сюда, разберёмся. {tail}"
        )
    if check == "needs_action":
        return (
            f"Документы в деле. По проверке требуется действие специалиста. "
            f"Пишите сюда, если нужны уточнения. {tail}"
        )
    return (
        f"Документы в деле. Статус проверки уточняем. {tail} "
        f"Пишите сюда, если нужны пояснения."
    )


def _base_reply(status: ClientCaseStatus) -> str:
    if status.kind == "staff_active":
        return ""
    if status.kind == "no_docs":
        return (
            "Пришлите документы, которые хотите проверить. "
            "Файлы можно присылать прямо в этот чат — PDF или фото."
        )
    if status.kind == "receiving":
        return (
            "Документы получили. Сейчас обрабатываем — повторно присылать "
            "те же файлы не нужно. Напишем сюда, когда сверим комплект."
        )
    if status.kind == "checking":
        check = str(status.check_status or "").strip().lower()
        if check == "queued":
            return (
                "Проверка ожидает запуска. Подождите, пожалуйста. "
                "Повторно комплект присылать не нужно."
            )
        return (
            "Проверка выполняется. Подождите, пожалуйста. "
            "Повторно комплект присылать не нужно."
        )
    if status.kind == "missing":
        need = " и ".join(
            _MISSING_RU[c] for c in status.missing_buckets if c in _MISSING_RU
        )
        have_bits = []
        if "ils" in status.have_buckets:
            have_bits.append("выписку о стаже")
        if "labor" in status.have_buckets:
            have_bits.append("трудовую")
        got = ""
        if have_bits:
            got = f"{' и '.join(have_bits).capitalize()} уже в деле. "
        return (
            f"{got}Для продолжения нужна {need} — если вы её ещё не отправляли, "
            "пришлите сюда в чат."
        )
    if status.kind == "error":
        detail = status.last_error or "задержка при обработке"
        return (
            f"По документам возникла задержка: {detail}. "
            "Специалист разберётся и напишет сюда. "
            "Повторно те же файлы присылать не нужно, если не попросим."
        )
    if status.kind == "result_ready":
        return status.result_summary or "Проверка комплекта завершена."
    # kit_ready_no_analysis: реестр типов есть, краткий анализ ещё не факт.
    return (
        "Базовый комплект получен. Краткая предварительная проверка "
        "ещё не запущена. Повторно присылать те же файлы не нужно. "
        "Мы готовим документы и план — обращение через СФР или Госуслуги "
        "подаёте вы сами. Решение принимает СФР."
    )


def _brief_summary_for_case(
    case_id: str,
    *,
    docs: list[dict[str, Any]],
) -> tuple[str | None, bool]:
    """Читает краткий разбор из intake по max_user_id дела."""
    del docs
    cid = str(case_id or "").strip()
    if not cid:
        return None, False
    try:
        import sfrfr.services.brief_analysis as ba
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.integrations.max.intake import get_intake_store

        case = CaseRepository().get_case_row(cid) or {}
        clients = case.get("clients") or {}
        if isinstance(clients, list):
            clients = clients[0] if clients else {}
        mid = str((clients or {}).get("max_user_id") or "").strip()
        if not mid:
            return None, False
        store = get_intake_store()
        store.reload()
        rec = store.get_active(mid)
        if rec is None:
            return None, False
        answers = rec.q_answers or {}
        if str(answers.get(ba.STATUS_KEY) or "") != ba.STATUS_COMPLETED:
            return None, False
        if str(answers.get(ba.SUMMARY_SHOWN_KEY) or "") != "1":
            return None, False
        summary = str(answers.get(ba.SUMMARY_KEY) or "").strip()
        current = str(answers.get(ba.CURRENT_KEY) or "") == "1"
        return (summary or None), current
    except Exception:  # noqa: BLE001
        return None, False


def _docs_ingest_pending(docs: list[dict[str, Any]]) -> bool:
    for doc in docs:
        status = str(doc.get("ingest_status") or "").lower()
        cloud = str(doc.get("cloud_status") or "").lower()
        if status in _PENDING_INGEST or cloud == "pending":
            return True
    return False


def _docs_ingest_failed(docs: list[dict[str, Any]]) -> bool:
    for doc in docs:
        status = str(doc.get("ingest_status") or "").lower()
        cloud = str(doc.get("cloud_status") or "").lower()
        if status in _FAILED_INGEST or cloud == "failed":
            return True
    return False
