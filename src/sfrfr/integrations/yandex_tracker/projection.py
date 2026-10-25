"""Проекция пенсионного дела → поля карточки Трекера.

Без ПДн. Оплата/подача/доставка не подтверждаются из Трекера —
только отображение уже подтверждённых фактов из БД.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sfrfr.integrations.yandex_tracker.client import TrackerClient, TrackerError


@dataclass(frozen=True, slots=True)
class CaseProjection:
    case_ref: str
    case_revision: int
    current_stage: str
    next_action: str
    waiting_on: str
    sync_status: str = "ok"
    analysis_payment: str = "unknown"
    appeals_payment: str = "unknown"
    escalation_payment: str = "unknown"


@dataclass(frozen=True, slots=True)
class ProjectionSyncResult:
    ok: bool
    issue_key: str
    case_revision: int
    tracker_version: int | None = None
    skipped: bool = False
    reason: str | None = None
    outcome_unknown: bool = False


DEFAULT_FIELD_KEYS = (
    "case_ref",
    "current_stage",
    "case_revision",
    "next_action",
    "waiting_on",
    "sync_status",
    "analysis_payment",
    "appeals_payment",
    "escalation_payment",
)


def parse_field_ids_json(raw: str) -> dict[str, str]:
    """Разобрать TRACKER_CASE_FIELD_IDS_JSON → {logical_name: tracker_field_id}."""
    text = (raw or "").strip() or "{}"
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("tracker_field_ids_not_object")
    out: dict[str, str] = {}
    for key, value in data.items():
        if key in DEFAULT_FIELD_KEYS and isinstance(value, str) and value.strip():
            out[str(key)] = value.strip()
    return out


def build_tracker_fields(
    projection: CaseProjection,
    field_ids: Mapping[str, str],
) -> dict[str, Any]:
    """Собрать PATCH-тело только по известным id полей очереди."""
    values: dict[str, Any] = {
        "case_ref": projection.case_ref,
        "current_stage": projection.current_stage,
        "case_revision": projection.case_revision,
        "next_action": projection.next_action[:500],
        "waiting_on": projection.waiting_on,
        "sync_status": projection.sync_status,
        "analysis_payment": projection.analysis_payment,
        "appeals_payment": projection.appeals_payment,
        "escalation_payment": projection.escalation_payment,
    }
    out: dict[str, Any] = {}
    for logical, value in values.items():
        field_id = field_ids.get(logical)
        if not field_id:
            continue
        out[field_id] = value
    if not out:
        raise ValueError("no_tracker_field_ids_configured")
    return out


def projection_from_payload(payload: Mapping[str, Any]) -> CaseProjection:
    return CaseProjection(
        case_ref=str(payload.get("case_ref") or ""),
        case_revision=int(payload.get("case_revision") or 0),
        current_stage=str(payload.get("current_stage") or "unknown"),
        next_action=str(payload.get("next_action") or ""),
        waiting_on=str(payload.get("waiting_on") or "staff"),
        sync_status=str(payload.get("sync_status") or "ok"),
        analysis_payment=str(payload.get("analysis_payment") or "unknown"),
        appeals_payment=str(payload.get("appeals_payment") or "unknown"),
        escalation_payment=str(payload.get("escalation_payment") or "unknown"),
    )


async def sync_case_projection(
    client: TrackerClient,
    *,
    issue_key: str,
    field_ids: Mapping[str, str],
    projection: CaseProjection,
    remote_revision_field: str | None = None,
) -> ProjectionSyncResult:
    """Обновить поля карточки. При outcome_unknown не считает sync успешным."""
    try:
        issue = await client.get_issue(issue_key)
    except TrackerError as exc:
        return ProjectionSyncResult(
            ok=False,
            issue_key=issue_key,
            case_revision=projection.case_revision,
            reason=exc.reason,
            outcome_unknown=exc.outcome_unknown,
        )

    version = int(issue.get("version") or 0)
    rev_key = remote_revision_field or field_ids.get("case_revision")
    if rev_key:
        remote_rev = issue.get(rev_key)
        try:
            if remote_rev is not None and int(remote_rev) >= projection.case_revision:
                return ProjectionSyncResult(
                    ok=True,
                    issue_key=issue_key,
                    case_revision=projection.case_revision,
                    tracker_version=version,
                    skipped=True,
                    reason="already_synced",
                )
        except (TypeError, ValueError):
            pass

    try:
        fields = build_tracker_fields(projection, field_ids)
        updated = await client.update_fields(issue_key, fields, version=version)
    except TrackerError as exc:
        return ProjectionSyncResult(
            ok=False,
            issue_key=issue_key,
            case_revision=projection.case_revision,
            reason=exc.reason,
            outcome_unknown=exc.outcome_unknown,
        )
    except ValueError as exc:
        return ProjectionSyncResult(
            ok=False,
            issue_key=issue_key,
            case_revision=projection.case_revision,
            reason=str(exc),
        )

    return ProjectionSyncResult(
        ok=True,
        issue_key=issue_key,
        case_revision=projection.case_revision,
        tracker_version=int(updated.get("version") or version),
    )
