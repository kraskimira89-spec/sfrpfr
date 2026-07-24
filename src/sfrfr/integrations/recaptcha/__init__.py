"""reCAPTCHA Enterprise: проверка токена для публичных лидов."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.google_sa import access_token, load_service_account_info

_RECAPTCHA_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class RecaptchaVerifier:
    def __init__(
        self,
        *,
        credentials_json: str | None = None,
        project_id: str | None = None,
        site_key: str | None = None,
        min_score: float | None = None,
    ) -> None:
        settings = get_settings()
        self._credentials_raw = (
            credentials_json
            if credentials_json is not None
            else settings.recaptcha_credentials_json
        ).strip()
        self.project_id = (
            project_id if project_id is not None else settings.recaptcha_project_id
        ).strip()
        self.site_key = (
            site_key if site_key is not None else settings.recaptcha_site_key
        ).strip()
        self.min_score = (
            float(min_score)
            if min_score is not None
            else float(settings.recaptcha_min_score or 0.5)
        )

    @property
    def configured(self) -> bool:
        return bool(self._credentials_raw and self.project_id and self.site_key)

    def verify(
        self,
        token: str,
        *,
        expected_action: str = "lead",
        user_ip: str | None = None,
    ) -> dict[str, Any]:
        """Вернуть ok/score; не логировать token."""
        if not self.configured:
            return {
                "ok": False,
                "skipped": True,
                "reason": "reCAPTCHA not configured",
            }
        tok = (token or "").strip()
        if not tok:
            return {"ok": False, "error": "empty_token"}

        try:
            info = load_service_account_info(
                self._credentials_raw,
                env_name="RECAPTCHA_CREDENTIALS_JSON",
            )
            bearer = access_token(info, scopes=[_RECAPTCHA_SCOPE])
            url = (
                f"https://recaptchaenterprise.googleapis.com/v1/"
                f"projects/{self.project_id}/assessments"
            )
            event: dict[str, Any] = {
                "token": tok,
                "siteKey": self.site_key,
                "expectedAction": expected_action,
            }
            if user_ip:
                event["userIpAddress"] = user_ip
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {bearer}",
                        "Content-Type": "application/json",
                    },
                    json={"event": event},
                )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:400],
                }
            body = resp.json() or {}
            token_props = body.get("tokenProperties") or {}
            risk = body.get("riskAnalysis") or {}
            valid = bool(token_props.get("valid"))
            action = str(token_props.get("action") or "")
            score = float(risk.get("score") or 0.0)
            action_ok = (not expected_action) or action == expected_action or action == ""
            ok = valid and action_ok and score >= self.min_score
            return {
                "ok": ok,
                "valid": valid,
                "score": score,
                "action": action,
                "min_score": self.min_score,
                "reasons": risk.get("reasons") or [],
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
