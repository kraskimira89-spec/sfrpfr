"""Live-проверка сайта не должна падать на медленном chunked-ответе."""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.yandex_webmaster_remediate import (  # noqa: E402
    _fetch,
    _http_label,
)


def test_fetch_returns_zero_status_on_read_timeout(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    status, headers, body = _fetch("https://proverkastaza.ru/")

    assert status == 0
    assert headers == {}
    assert body == b""
    assert calls["n"] == 2


def test_fetch_retries_once_after_timeout(monkeypatch) -> None:
    state = {"n": 0}

    class FakeResp:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def read(self) -> bytes:
            return b"ok"

        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *exc_info: object) -> bool:
            return False

    def fake_urlopen(req, timeout=None):
        state["n"] += 1
        if state["n"] == 1:
            raise TimeoutError("The read operation timed out")
        return FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    status, _, body = _fetch("https://proverkastaza.ru/")

    assert status == 200
    assert body == b"ok"
    assert state["n"] == 2


def test_http_label_marks_timeout_status() -> None:
    assert _http_label(0) == "timeout"
    assert _http_label(404) == "404"
