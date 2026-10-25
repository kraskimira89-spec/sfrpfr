from sfrfr.services.case_tracker_pilot import is_case_sync_allowlisted, parse_sync_allowlist


def test_parse_allowlist_csv() -> None:
    ids = parse_sync_allowlist(" a,b , ,c ")
    assert ids == {"a", "b", "c"}


def test_allowlist_empty_rejects(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "sfrfr.services.case_tracker_pilot.get_settings",
        lambda: type("S", (), {"tracker_case_sync_allowlist": ""})(),
    )
    assert is_case_sync_allowlisted("any") is False


def test_allowlist_match(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "sfrfr.services.case_tracker_pilot.get_settings",
        lambda: type(
            "S",
            (),
            {"tracker_case_sync_allowlist": "11111111-1111-1111-1111-111111111111"},
        )(),
    )
    assert is_case_sync_allowlisted("11111111-1111-1111-1111-111111111111") is True
    assert is_case_sync_allowlisted("other") is False
