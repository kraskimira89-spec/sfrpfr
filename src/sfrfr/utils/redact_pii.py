from __future__ import annotations

import re


def mask_snils(value: str) -> str:
    """Маскирует СНИЛС для логов и UI."""
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        return "***-***-*** **"
    return f"***-***-{digits[6:9]} {digits[9:]}"


def redact_fio(full_name: str) -> str:
    parts = full_name.split()
    if not parts:
        return "***"
    return parts[0][0] + "***"
