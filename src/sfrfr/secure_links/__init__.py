"""Secure action links (MAX-first Sprint 1) — фундамент за feature flag."""

from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.secure_links.service import SecureActionLinkService
from sfrfr.secure_links.token import (
    PURPOSES,
    generate_raw_token,
    hash_token,
    token_prefix,
)

__all__ = [
    "PURPOSES",
    "SecureActionLinkService",
    "SecureLinkDenied",
    "SecureLinksDisabled",
    "generate_raw_token",
    "hash_token",
    "token_prefix",
]
