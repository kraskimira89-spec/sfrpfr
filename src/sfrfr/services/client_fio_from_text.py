"""Извлечение ФИО из первого OCR/текста документа и запись в clients.

Не логируем сами ФИО. При нескольких кандидатах — только labeled / с отчеством.
Не перезаписываем уже уверенное полное ФИО более слабым сигналом.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from sfrfr.utils.person_name import (
    ParsedPersonName,
    is_placeholder_name,
    parse_person_name,
)

logger = logging.getLogger(__name__)

SourceKind = Literal["document", "client_text"]

# Подписи в ИЛС / трудовой / заявлениях (без захвата ПДн в лог).
_NAME_TOKEN = r"[А-ЯЁа-яё][А-ЯЁа-яё\-]*"

_LABELED_FIO_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:"
    r"ф\.?\s*и\.?\s*о\.?"
    r"|фамилия(?:\s*,?\s*имя)?(?:\s*,?\s*отчество)?"
    r"|застрахованн\w*"
    r"|владелец\s+сч[её]та"
    r"|заявител\w*"
    r")\s*[:\-–—]?\s*"
    rf"({_NAME_TOKEN}(?:[ \t]+{_NAME_TOKEN}){{1,3}})"
)

# Свободная строка «Фамилия Имя Отчество» (отчество обязательно).
_LINE_FIO_RE = re.compile(
    rf"(?m)^[ \t]*({_NAME_TOKEN})[ \t]+({_NAME_TOKEN})[ \t]+"
    rf"({_NAME_TOKEN}(?:ович|евич|ич|овна|евна|ична|инична))[ \t]*$",
    re.IGNORECASE,
)

# Клиент: «Меня зовут …» / «Я — …»
_CLIENT_INTRO_RE = re.compile(
    rf"(?i)(?:меня\s+зовут|я\s*[-—:]\s*|мо[её]\s+имя\s*)"
    rf"[ \t]*({_NAME_TOKEN}(?:[ \t]+{_NAME_TOKEN}){{1,3}})"
)

_CONF_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def extract_fio_from_text(
    text: str | None,
    *,
    source: SourceKind = "document",
) -> ParsedPersonName | None:
    """Вернуть лучший кандидат ФИО или None."""
    blob = str(text or "")
    if len(blob.strip()) < 8:
        return None

    candidates: list[ParsedPersonName] = []

    if source == "document":
        for match in _LABELED_FIO_RE.finditer(blob):
            parsed = parse_person_name(match.group(1))
            if parsed.is_usable and parsed.given:
                # Подпись в документе повышает уверенность.
                if parsed.confidence == "medium" and parsed.patronymic:
                    parsed = ParsedPersonName(
                        raw=parsed.raw,
                        surname=parsed.surname,
                        given=parsed.given,
                        patronymic=parsed.patronymic,
                        confidence="high",
                        salutation=parsed.salutation,
                        display=parsed.display,
                        needs_confirm=False,
                    )
                candidates.append(parsed)
        for match in _LINE_FIO_RE.finditer(blob):
            parsed = parse_person_name(
                f"{match.group(1)} {match.group(2)} {match.group(3)}"
            )
            if parsed.is_usable:
                candidates.append(parsed)
    else:
        intro = _CLIENT_INTRO_RE.search(blob)
        if intro:
            parsed = parse_person_name(intro.group(1))
            if parsed.is_usable:
                candidates.append(parsed)

    if not candidates:
        return None

    # Предпочитаем ФИО с фамилией+отчеством и максимальной уверенностью.
    def _key(p: ParsedPersonName) -> tuple[int, int, int]:
        return (
            _CONF_RANK.get(p.confidence, 0),
            1 if p.surname and p.patronymic else 0,
            1 if p.patronymic else 0,
        )

    best = max(candidates, key=_key)
    # Несколько разных high с фамилией — неоднозначно, не пишем.
    def _identity(p: ParsedPersonName) -> str:
        return " ".join(
            x for x in (p.surname, p.given, p.patronymic) if x
        ).casefold()

    strong = [
        p
        for p in candidates
        if p.confidence == "high" and p.surname and p.given and p.patronymic
    ]
    identities = {_identity(p) for p in strong if _identity(p)}
    if len(identities) > 1:
        logger.info("client_fio_from_text ambiguous candidates=%s", len(identities))
        return None
    if _CONF_RANK.get(best.confidence, 0) < _CONF_RANK["medium"]:
        return None
    return best


def should_replace_client_fio(
    current_full_name: str | None,
    incoming: ParsedPersonName,
) -> bool:
    """Можно ли записать incoming поверх текущего full_name."""
    if not incoming.is_usable or not incoming.display:
        return False
    current = (current_full_name or "").strip()
    if is_placeholder_name(current) or not current:
        return True
    cur = parse_person_name(current)
    # Уже полное уверенное ФИО — не трогаем слабее/равным без отчества→с отчеством.
    if (
        cur.confidence == "high"
        and cur.surname
        and cur.given
        and cur.patronymic
        and cur.display
    ):
        return False
    # Документ дал ФИО с отчеством, в карточке только имя из MAX.
    if incoming.patronymic and not cur.patronymic:
        return True
    if incoming.surname and not cur.surname and incoming.confidence == "high":
        return True
    return _CONF_RANK.get(incoming.confidence, 0) > _CONF_RANK.get(
        cur.confidence, 0
    )


def maybe_apply_client_fio_from_text(
    *,
    case_id: str,
    text: str | None,
    source: SourceKind = "document",
    actor_id: str = "system:fio_extract",
) -> dict[str, Any] | None:
    """Извлечь ФИО и при разрешении записать в clients.full_name.

    Возвращает краткий статус без ПДн: applied / skipped / none.
    """
    cid = str(case_id or "").strip()
    if not cid:
        return {"ok": False, "reason": "no_case"}

    parsed = extract_fio_from_text(text, source=source)
    if parsed is None or not parsed.display:
        return {"ok": True, "reason": "no_candidate"}

    try:
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.db.session import get_supabase_client
        from sfrfr.integrations.yandex_workspace import sync_case_disk_folder_name_safe
    except Exception as exc:  # noqa: BLE001
        logger.debug("fio extract imports failed: %s", type(exc).__name__)
        return {"ok": False, "reason": "import"}

    try:
        case = CaseRepository().get_case_row(cid) or {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("fio extract case load failed: %s", type(exc).__name__)
        return {"ok": False, "reason": "case_load"}

    client_id = str(case.get("client_id") or "").strip()
    clients = case.get("clients") or {}
    if isinstance(clients, list):
        clients = clients[0] if clients else {}
    if not client_id:
        client_id = str((clients or {}).get("id") or "").strip()
    current = str((clients or {}).get("full_name") or "").strip() or None

    if not client_id:
        return {"ok": False, "reason": "no_client"}
    if not should_replace_client_fio(current, parsed):
        return {"ok": True, "reason": "keep_current"}

    display = parsed.display
    try:
        client = get_supabase_client()
        client.table("clients").update({"full_name": display}).eq(
            "id", client_id
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fio extract update failed: %s", type(exc).__name__)
        return {"ok": False, "reason": "update"}

    try:
        CaseRepository().audit(
            cid, actor_id, f"client_fio_from_text:{source}"
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        sync_case_disk_folder_name_safe(cid, full_name=display)
    except Exception:  # noqa: BLE001
        pass

    # Без ФИО в логе — только факт применения.
    logger.info("client_fio_from_text applied case=%s source=%s", cid[:8], source)
    return {
        "ok": True,
        "reason": "applied",
        "confidence": parsed.confidence,
        "has_patronymic": bool(parsed.patronymic),
    }
