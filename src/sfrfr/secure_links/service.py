"""Сервис create / verify / revoke / supersede secure action links."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sfrfr.core.config import Settings, get_settings
from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.secure_links.repository import SecureActionLinksRepo, SecureActionLinksRepository
from sfrfr.secure_links.token import (
    PURPOSES,
    generate_raw_token,
    hash_token,
    resolve_pepper,
    token_prefix,
)

DEFAULT_TTL_HOURS = 24


@dataclass(frozen=True)
class IssuedSecureLink:
    """Результат create: raw_token только здесь, не в StoredLink."""

    id: str
    raw_token: str
    token_prefix: str
    purpose: str
    case_id: str
    expires_at: datetime
    max_uses: int
    status: str


@dataclass(frozen=True)
class StoredSecureLink:
    """Хранимое представление без raw_token."""

    id: str
    token_hash: str
    token_prefix: str
    purpose: str
    status: str
    case_id: str
    max_uses: int
    use_count: int
    expires_at: datetime
    resource_id: str | None = None
    resource_type: str | None = None
    max_user_id: str | None = None
    revoked_at: datetime | None = None
    consumed_at: datetime | None = None
    issued_via: str = "system"
    meta: dict[str, Any] | None = None

    def storage_dict(self) -> dict[str, Any]:
        """Словарь для БД/аудита — без raw_token."""
        return {
            "id": self.id,
            "token_hash": self.token_hash,
            "token_prefix": self.token_prefix,
            "purpose": self.purpose,
            "status": self.status,
            "case_id": self.case_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "max_user_id": self.max_user_id,
            "max_uses": self.max_uses,
            "use_count": self.use_count,
            "expires_at": self.expires_at.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "consumed_at": self.consumed_at.isoformat() if self.consumed_at else None,
            "issued_via": self.issued_via,
            "meta": dict(self.meta or {}),
        }


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _row_to_stored(row: dict[str, Any]) -> StoredSecureLink:
    expires = _parse_dt(row.get("expires_at"))
    if expires is None:
        raise SecureLinkDenied("invalid_row")
    return StoredSecureLink(
        id=str(row["id"]),
        token_hash=str(row["token_hash"]),
        token_prefix=str(row.get("token_prefix") or ""),
        purpose=str(row["purpose"]),
        status=str(row.get("status") or "active"),
        case_id=str(row["case_id"]),
        max_uses=int(row.get("max_uses") or 1),
        use_count=int(row.get("use_count") or 0),
        expires_at=expires,
        resource_id=str(row["resource_id"]) if row.get("resource_id") else None,
        resource_type=str(row["resource_type"]) if row.get("resource_type") else None,
        max_user_id=str(row["max_user_id"]) if row.get("max_user_id") else None,
        revoked_at=_parse_dt(row.get("revoked_at")),
        consumed_at=_parse_dt(row.get("consumed_at")),
        issued_via=str(row.get("issued_via") or "system"),
        meta=dict(row.get("meta") or {}),
    )


class SecureActionLinkService:
    def __init__(
        self,
        repo: SecureActionLinksRepo | None = None,
        *,
        settings: Settings | None = None,
        enabled: bool | None = None,
        pepper: bytes | None = None,
        now_fn: Any | None = None,
    ) -> None:
        self.repo: SecureActionLinksRepo = repo or SecureActionLinksRepository()
        self.settings = settings or get_settings()
        self._enabled_override = enabled
        self._pepper = pepper
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    def _enabled(self) -> bool:
        if self._enabled_override is not None:
            return bool(self._enabled_override)
        return bool(self.settings.secure_action_links_enabled)

    def _require_enabled(self) -> None:
        if not self._enabled():
            raise SecureLinksDisabled()

    def _pepper_bytes(self) -> bytes:
        if self._pepper is not None:
            return self._pepper
        return resolve_pepper(self.settings)

    def _audit(
        self,
        *,
        link_id: str,
        case_id: str,
        event_type: str,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        meta = dict(metadata or {})
        # Защита от случайных ПДн-ключей в metadata
        for forbidden in ("snils", "email", "phone", "fio", "passport", "ils"):
            meta.pop(forbidden, None)
        self.repo.insert_event(
            {
                "id": str(uuid4()),
                "link_id": link_id,
                "case_id": case_id,
                "event_type": event_type,
                "actor": actor,
                "metadata": meta,
                "created_at": self._now_fn().isoformat(),
            }
        )

    def create(
        self,
        *,
        case_id: str,
        purpose: str,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        max_uses: int = 1,
        resource_id: str | None = None,
        resource_type: str | None = None,
        max_user_id: str | None = None,
        issued_via: str = "system",
        created_by: str | None = None,
        meta: dict[str, Any] | None = None,
        supersede_active: bool = True,
        actor: str | None = None,
    ) -> IssuedSecureLink:
        self._require_enabled()
        if purpose not in PURPOSES:
            raise SecureLinkDenied("invalid_purpose")
        if max_uses < 1:
            raise SecureLinkDenied("invalid_max_uses")
        if ttl_hours < 1:
            raise SecureLinkDenied("invalid_ttl")

        now = self._now_fn()
        expires_at = now + timedelta(hours=ttl_hours)
        raw = generate_raw_token()
        prefix = token_prefix(raw)
        digest = hash_token(raw, pepper=self._pepper_bytes())
        link_id = str(uuid4())

        if supersede_active:
            for old in self.repo.list_active_for_case_purpose(case_id, purpose):
                self._mark_superseded(old, new_id=link_id, actor=actor)

        row: dict[str, Any] = {
            "id": link_id,
            "token_hash": digest,
            "token_prefix": prefix,
            "purpose": purpose,
            "status": "active",
            "case_id": case_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "max_user_id": max_user_id,
            "max_uses": max_uses,
            "use_count": 0,
            "expires_at": expires_at.isoformat(),
            "issued_via": issued_via,
            "created_by": created_by,
            "meta": dict(meta or {}),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        stored = self.repo.insert_link(row)
        # raw не должен оказаться в row / storage
        assert "raw_token" not in stored
        assert "raw_token" not in row

        self._audit(
            link_id=link_id,
            case_id=case_id,
            event_type="created",
            actor=actor or created_by or issued_via,
            metadata={"purpose": purpose, "token_prefix": prefix},
        )
        return IssuedSecureLink(
            id=link_id,
            raw_token=raw,
            token_prefix=prefix,
            purpose=purpose,
            case_id=case_id,
            expires_at=expires_at,
            max_uses=max_uses,
            status="active",
        )

    def verify(
        self,
        raw_token: str,
        *,
        purpose: str | None = None,
        consume: bool = False,
        actor: str | None = None,
    ) -> StoredSecureLink:
        self._require_enabled()
        if not (raw_token or "").strip():
            raise SecureLinkDenied("missing_token")

        digest = hash_token(raw_token.strip(), pepper=self._pepper_bytes())
        row = self.repo.get_by_hash(digest)
        if not row:
            raise SecureLinkDenied("not_found")

        link = _row_to_stored(row)
        now = self._now_fn()
        deny_reason = self._validate(link, purpose=purpose, now=now)
        if deny_reason:
            self._audit(
                link_id=link.id,
                case_id=link.case_id,
                event_type="denied",
                actor=actor,
                metadata={"reason": deny_reason, "token_prefix": link.token_prefix},
            )
            raise SecureLinkDenied(deny_reason)

        if consume:
            return self._consume(link, actor=actor)

        self._audit(
            link_id=link.id,
            case_id=link.case_id,
            event_type="verified",
            actor=actor,
            metadata={"purpose": link.purpose, "token_prefix": link.token_prefix},
        )
        return link

    def revoke(
        self,
        link_id: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> StoredSecureLink:
        self._require_enabled()
        row = self.repo.get_by_id(link_id)
        if not row:
            raise SecureLinkDenied("not_found")
        link = _row_to_stored(row)
        now = self._now_fn()
        updated = self.repo.update_link(
            link_id,
            {
                "status": "revoked",
                "revoked_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )
        self._audit(
            link_id=link_id,
            case_id=link.case_id,
            event_type="revoked",
            actor=actor,
            metadata={"reason": reason or "manual", "token_prefix": link.token_prefix},
        )
        return _row_to_stored({**row, **updated})

    def supersede(
        self,
        old_link_id: str,
        *,
        case_id: str,
        purpose: str,
        actor: str | None = None,
        **create_kwargs: Any,
    ) -> IssuedSecureLink:
        """Явно supersede старую + create новую (create тоже умеет supersede_active)."""
        self._require_enabled()
        old = self.repo.get_by_id(old_link_id)
        issued = self.create(
            case_id=case_id,
            purpose=purpose,
            supersede_active=False,
            actor=actor,
            **create_kwargs,
        )
        if old:
            self._mark_superseded(old, new_id=issued.id, actor=actor)
        return issued

    def _mark_superseded(
        self,
        old: dict[str, Any],
        *,
        new_id: str,
        actor: str | None,
    ) -> None:
        now = self._now_fn()
        old_id = str(old["id"])
        self.repo.update_link(
            old_id,
            {
                "status": "superseded",
                "superseded_by": new_id,
                "revoked_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )
        self._audit(
            link_id=old_id,
            case_id=str(old["case_id"]),
            event_type="superseded",
            actor=actor,
            metadata={
                "superseded_by": new_id,
                "token_prefix": str(old.get("token_prefix") or ""),
            },
        )

    def _validate(
        self,
        link: StoredSecureLink,
        *,
        purpose: str | None,
        now: datetime,
    ) -> str | None:
        if link.status == "revoked":
            return "revoked"
        if link.status == "superseded":
            return "superseded"
        if link.status == "consumed":
            return "consumed"
        if link.status != "active":
            return "invalid_status"
        if link.revoked_at is not None:
            return "revoked"
        if link.expires_at <= now:
            return "expired"
        if link.use_count >= link.max_uses:
            return "max_uses"
        if purpose is not None and purpose != link.purpose:
            return "wrong_purpose"
        return None

    def _consume(self, link: StoredSecureLink, *, actor: str | None) -> StoredSecureLink:
        now = self._now_fn()
        new_count = link.use_count + 1
        fields: dict[str, Any] = {
            "use_count": new_count,
            "updated_at": now.isoformat(),
        }
        event = "verified"
        if new_count >= link.max_uses:
            fields["status"] = "consumed"
            fields["consumed_at"] = now.isoformat()
            event = "consumed"
        updated = self.repo.update_link(link.id, fields)
        self._audit(
            link_id=link.id,
            case_id=link.case_id,
            event_type=event,
            actor=actor,
            metadata={
                "purpose": link.purpose,
                "token_prefix": link.token_prefix,
                "use_count": new_count,
            },
        )
        row = {
            "id": link.id,
            "token_hash": link.token_hash,
            "token_prefix": link.token_prefix,
            "purpose": link.purpose,
            "status": fields.get("status", link.status),
            "case_id": link.case_id,
            "max_uses": link.max_uses,
            "use_count": new_count,
            "expires_at": link.expires_at.isoformat(),
            "resource_id": link.resource_id,
            "resource_type": link.resource_type,
            "max_user_id": link.max_user_id,
            "revoked_at": link.revoked_at.isoformat() if link.revoked_at else None,
            "consumed_at": fields.get("consumed_at"),
            "issued_via": link.issued_via,
            "meta": link.meta or {},
        }
        row.update({k: v for k, v in updated.items() if k in row or k in fields})
        return _row_to_stored(row)
