"""Имя папки дела на Яндекс.Диске / локальном зеркале.

Канон: «Фамилия Имя Отчество» (см. parse_person_name).
Без телефона/СНИЛС в пути; при отсутствии ФИО — UUID дела.
"""

from __future__ import annotations

import re

from sfrfr.utils.person_name import parse_person_name

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
# Запрет разделителей пути и опасных символов FS / Disk API.
_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_MULTI_SPACE = re.compile(r"\s+")


def format_case_disk_folder_name(
    full_name: str | None,
    *,
    case_id: str,
) -> str:
    """Папка дела: «Фамилия Имя Отчество» или UUID при пустом/мусорном ФИО."""
    cid = (case_id or "").strip()
    raw = _MULTI_SPACE.sub(" ", _FORBIDDEN_CHARS.sub(" ", full_name or "")).strip()
    parsed = parse_person_name(raw)
    label = (parsed.display or "").strip()
    if not label:
        return cid.lower() if _UUID_RE.match(cid) else cid
    safe = _MULTI_SPACE.sub(" ", label).strip(" ._")
    if not safe:
        return cid.lower() if _UUID_RE.match(cid) else cid
    return safe[:180]
