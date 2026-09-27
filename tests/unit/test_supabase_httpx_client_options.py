"""Клиент Supabase без устаревших timeout/verify у SyncPostgrestClient."""

from __future__ import annotations

import warnings

from sfrfr.db.session import _client_factory, supabase_client_options


def test_create_client_with_options_has_no_timeout_verify_deprecation() -> None:
    opts = supabase_client_options()
    assert opts.httpx_client is not None

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        client = _client_factory()("https://example.supabase.co", "test-anon-key", options=opts)
        _ = client.table("cases")

    msgs = [
        str(w.message)
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and ("timeout" in str(w.message) or "verify" in str(w.message))
    ]
    assert msgs == []
