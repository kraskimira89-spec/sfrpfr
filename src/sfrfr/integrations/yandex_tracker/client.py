"""Транспортный клиент Tracker API (async).

Не создаёт собственные retry-циклы для записей: неизвестный исход
обрабатывает worker через повторное чтение состояния.
Совместим с credentials из существующего пакета (OAuth + X-Org-ID /
X-Cloud-Org-ID). Не заменяет quality_issues / create_issue.
"""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

import httpx

from sfrfr.core.config import get_settings


class TrackerError(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        status_code: int | None = None,
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code
        self.outcome_unknown = outcome_unknown


class TrackerClient:
    def __init__(
        self,
        *,
        oauth_token: str,
        organization_id: str,
        organization_header: Literal["X-Org-ID", "X-Cloud-Org-ID"],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not oauth_token or not organization_id:
            raise ValueError("Tracker credentials are required")

        self._http = httpx.AsyncClient(
            base_url="https://api.tracker.yandex.net/v3/",
            headers={
                "Authorization": f"OAuth {oauth_token}",
                organization_header: organization_id,
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self) -> TrackerClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _segment(value: str) -> str:
        if not value.strip():
            raise ValueError("Empty API identifier")
        return quote(value, safe="")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        is_write = method not in {"GET", "HEAD"}

        try:
            response = await self._http.request(
                method,
                path,
                json=json,
                params=params,
            )
        except httpx.RequestError:
            raise TrackerError(
                "tracker_transport_error",
                outcome_unknown=is_write,
            ) from None

        if response.status_code >= 400:
            raise TrackerError(
                "tracker_http_error",
                status_code=response.status_code,
                outcome_unknown=(is_write and response.status_code >= 500),
            )

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            raise TrackerError(
                "tracker_invalid_response",
                outcome_unknown=is_write,
            ) from None

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"issues/{self._segment(issue_key)}",
        )
        if not isinstance(data, dict):
            raise TrackerError("tracker_invalid_issue")
        return data

    async def update_fields(
        self,
        issue_key: str,
        fields: dict[str, Any],
        *,
        version: int,
    ) -> dict[str, Any]:
        if "status" in fields:
            raise ValueError("Use execute_transition for status")

        data = await self._request(
            "PATCH",
            f"issues/{self._segment(issue_key)}",
            params={"version": str(version)},
            json=fields,
        )
        if not isinstance(data, dict):
            raise TrackerError(
                "tracker_invalid_update_response",
                outcome_unknown=True,
            )
        return data

    async def get_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"issues/{self._segment(issue_key)}/transitions",
        )
        if not isinstance(data, list):
            raise TrackerError("tracker_invalid_transitions")
        return data

    async def execute_transition(
        self,
        issue_key: str,
        transition_id: str,
        *,
        fields: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            "POST",
            (
                f"issues/{self._segment(issue_key)}/transitions/"
                f"{self._segment(transition_id)}/_execute"
            ),
            json=fields or {},
        )


def tracker_client_from_settings(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TrackerClient:
    """Собрать клиент из тех же env, что и quality STAZH-поток."""
    settings = get_settings()
    token = (settings.tracker_oauth_token or settings.tracker_token or "").strip()
    cloud = (settings.tracker_cloud_org_id or "").strip()
    org = (settings.tracker_org_id or "").strip()
    if cloud:
        header: Literal["X-Org-ID", "X-Cloud-Org-ID"] = "X-Cloud-Org-ID"
        org_id = cloud
    else:
        header = "X-Org-ID"
        org_id = org
    return TrackerClient(
        oauth_token=token,
        organization_id=org_id,
        organization_header=header,
        transport=transport,
    )
