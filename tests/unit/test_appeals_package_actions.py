"""Этап 8: audit-действия пакета первичных обращений."""

from sfrfr.services.message_dedupe import has_appeals_consent_accepted


def _has_package_action(rows: list[dict], prefix: str) -> bool:
    return any(str(r.get("action") or "").startswith(prefix) for r in rows)


def test_appeals_package_ready_and_delivered_prefixes() -> None:
    rows = [
        {"action": "appeals_package_ready"},
        {"action": "appeals_package_delivered:bot:x"},
    ]
    assert _has_package_action(rows, "appeals_package_ready")
    assert _has_package_action(rows, "appeals_package_delivered")
    assert not _has_package_action(rows, "appeals_consent_accepted")


def test_consent_helper_still_distinct() -> None:
    assert has_appeals_consent_accepted([{"action": "appeals_package_ready"}]) is False
    assert has_appeals_consent_accepted([{"action": "appeals_consent_accepted"}]) is True
