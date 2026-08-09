"""Нормализация рекламной атрибуции (UTM) для lead API и CRM."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

# Справочник ТЗ marketing-sales foundation §5
UTM_SOURCES = frozenset(
    {
        "yandex",
        "vk",
        "ok",
        "max",
        "dzen",
        "partner",
        "referral",
        "organic",
        "direct",
        "wordpress",
        "wordpress_wpforms",
        "unknown",
    }
)
UTM_MEDIA = frozenset(
    {
        "cpc",
        "paid_social",
        "organic_social",
        "seo",
        "referral",
        "email",
        "messenger",
        "offline",
        "unknown",
    }
)
AUDIENCE_SEGMENTS = frozenset(
    {
        "pre_retirement",
        "north_or_preferential",
        "relative",
        "pensioner_issue",
        "b2b_lawyer",
        "b2b_organization",
        "unknown",
    }
)
REGION_BUCKETS = frozenset({"north_priority", "other_russia", "unknown"})

_MAX_CAMPAIGN = 120
_MAX_CONTENT = 120
_MAX_TERM = 120
_MAX_VARIANT = 64
_MAX_REFERRAL = 64


def _clean(raw: str | None, *, max_len: int) -> str:
    if raw is None:
        return ""
    text = "".join(ch for ch in str(raw).strip() if ch.isprintable())
    # Не сохраняем URL целиком и секреты
    if "://" in text or "token=" in text.lower() or "password" in text.lower():
        return ""
    return text[:max_len]


def _pick(raw: str | None, allowed: frozenset[str], *, fallback: str = "unknown") -> str:
    value = _clean(raw, max_len=64).lower().replace(" ", "_")
    if not value:
        return fallback
    if value in allowed:
        return value
    # Частые алиасы
    aliases = {
        "yandex_direct": "yandex",
        "ya": "yandex",
        "vkontakte": "vk",
        "odnoklassniki": "ok",
        "zen": "dzen",
        "cpm": "cpc",
        "ppc": "cpc",
        "social": "paid_social",
    }
    mapped = aliases.get(value)
    if mapped and mapped in allowed:
        return mapped
    return fallback


@dataclass(frozen=True)
class LeadAttribution:
    source: str = "unknown"
    medium: str = "unknown"
    campaign: str = ""
    content: str = ""
    term: str = ""
    landing_variant: str = ""
    audience_segment: str = "unknown"
    region_bucket: str = "unknown"
    referral_code: str = ""
    first_source: str = "unknown"
    last_source: str = "unknown"
    first_touch_at: str = ""
    last_touch_at: str = ""

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}


def normalize_attribution(
    *,
    source: str | None = None,
    medium: str | None = None,
    campaign: str | None = None,
    content: str | None = None,
    term: str | None = None,
    landing_variant: str | None = None,
    audience_segment: str | None = None,
    region_bucket: str | None = None,
    referral_code: str | None = None,
    first_source: str | None = None,
    last_source: str | None = None,
    first_touch_at: str | None = None,
    last_touch_at: str | None = None,
) -> LeadAttribution:
    """Неизвестные значения не роняют лид — уходят в unknown / truncate."""
    src = _pick(source, UTM_SOURCES, fallback="unknown")
    # Обратная совместимость: wordpress* оставляем как source
    if (source or "").strip().lower() in {"wordpress", "wordpress_wpforms"}:
        src = (source or "").strip().lower()
    med = _pick(medium, UTM_MEDIA, fallback="unknown")
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    wp_sources = UTM_SOURCES | {"wordpress", "wordpress_wpforms"}
    first = _pick(first_source or source, wp_sources, fallback=src)
    last = _pick(last_source or source, wp_sources, fallback=src)
    if (source or "").strip().lower() in {"wordpress", "wordpress_wpforms"}:
        first = (first_source or source or src).strip().lower()[:64] or src
        last = (last_source or source or src).strip().lower()[:64] or src
    return LeadAttribution(
        source=src,
        medium=med,
        campaign=_clean(campaign, max_len=_MAX_CAMPAIGN),
        content=_clean(content, max_len=_MAX_CONTENT),
        term=_clean(term, max_len=_MAX_TERM),
        landing_variant=_clean(landing_variant, max_len=_MAX_VARIANT),
        audience_segment=_pick(audience_segment, AUDIENCE_SEGMENTS),
        region_bucket=_pick(region_bucket, REGION_BUCKETS),
        referral_code=_clean(referral_code, max_len=_MAX_REFERRAL),
        first_source=first,
        last_source=last,
        first_touch_at=_clean(first_touch_at, max_len=40) or now,
        last_touch_at=_clean(last_touch_at, max_len=40) or now,
    )


def metrika_params_allowlist(raw: dict[str, Any] | None) -> dict[str, str]:
    """Только параметры §7.3 — без ПДн."""
    if not raw:
        return {}
    allowed = ("placement", "page_type", "audience_segment", "campaign_code", "region_bucket")
    out: dict[str, str] = {}
    for key in allowed:
        val = _clean(str(raw.get(key) or ""), max_len=64)
        if val:
            out[key] = val
    return out
