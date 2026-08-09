"""Тесты нормализации UTM-атрибуции."""

from __future__ import annotations

from sfrfr.marketing.attribution import metrika_params_allowlist, normalize_attribution


def test_normalize_empty_defaults() -> None:
    attr = normalize_attribution()
    assert attr.source == "unknown"
    assert attr.medium == "unknown"
    assert attr.audience_segment == "unknown"


def test_normalize_full_utm() -> None:
    attr = normalize_attribution(
        source="yandex",
        medium="cpc",
        campaign="north_q3",
        content="ad1",
        term="северный стаж",
        audience_segment="north_or_preferential",
        region_bucket="north_priority",
        landing_variant="v1",
        referral_code="partner-a",
    )
    assert attr.source == "yandex"
    assert attr.medium == "cpc"
    assert attr.campaign == "north_q3"
    assert attr.audience_segment == "north_or_preferential"
    assert attr.referral_code == "partner-a"


def test_unknown_values_do_not_raise() -> None:
    attr = normalize_attribution(
        source="weird!!!",
        medium="xxx",
        campaign="https://evil.example/path?token=secret",
        audience_segment="hack",
    )
    assert attr.source == "unknown"
    assert attr.medium == "unknown"
    assert attr.campaign == ""  # URL stripped
    assert attr.audience_segment == "unknown"


def test_wordpress_source_preserved() -> None:
    attr = normalize_attribution(source="wordpress_wpforms", medium="seo")
    assert attr.source == "wordpress_wpforms"
    assert attr.medium == "seo"


def test_metrika_params_strip_pii() -> None:
    out = metrika_params_allowlist(
        {
            "placement": "hero",
            "email": "a@b.c",
            "case_id": "uuid",
            "audience_segment": "relative",
            "phone": "+7900",
        }
    )
    assert out == {"placement": "hero", "audience_segment": "relative"}
    assert "email" not in out
    assert "case_id" not in out
