"""Юнит-тесты Yandex SmartCaptcha verifier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.integrations.smartcaptcha import SmartCaptchaVerifier


def test_not_configured_skipped() -> None:
    v = SmartCaptchaVerifier(server_key="")
    assert v.configured is False
    assert v.verify("tok").get("skipped") is True


def test_empty_token() -> None:
    v = SmartCaptchaVerifier(server_key="secret")
    assert v.verify("").get("error") == "empty_token"


def test_ok_status() -> None:
    v = SmartCaptchaVerifier(server_key="secret")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "host": "example.ru"}
    with patch("sfrfr.integrations.smartcaptcha.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
        out = v.verify("tok", user_ip="1.2.3.4")
    assert out["ok"] is True
    assert out["host"] == "example.ru"


def test_failed_status() -> None:
    v = SmartCaptchaVerifier(server_key="secret")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "failed", "message": "Invalid or expired Token"}
    with patch("sfrfr.integrations.smartcaptcha.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
        out = v.verify("tok")
    assert out["ok"] is False


def test_http_error_fail_open() -> None:
    v = SmartCaptchaVerifier(server_key="secret")
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "busy"
    with patch("sfrfr.integrations.smartcaptcha.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
        out = v.verify("tok")
    assert out["ok"] is True
    assert out.get("degraded") is True
