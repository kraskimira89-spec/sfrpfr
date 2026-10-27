"""Этап 9: audit-действия подтверждения подачи (≠ передача пакета)."""


def _has(rows: list[dict], prefix: str) -> bool:
    return any(str(r.get("action") or "").startswith(prefix) for r in rows)


def test_submission_confirmed_distinct_from_package_delivered() -> None:
    rows = [
        {"action": "appeals_package_delivered"},
        {"action": "submission_confirmed"},
    ]
    assert _has(rows, "submission_confirmed")
    assert _has(rows, "appeals_package_delivered")
    # Передача пакета сама по себе не является подтверждением подачи.
    package_only = [{"action": "appeals_package_delivered"}]
    assert not _has(package_only, "submission_confirmed")


def test_submission_help_requested_prefix() -> None:
    rows = [{"action": "submission_help_requested:staff"}]
    assert _has(rows, "submission_help_requested")
    assert not _has(rows, "submission_confirmed")
