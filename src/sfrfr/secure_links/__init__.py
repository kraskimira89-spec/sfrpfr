"""Secure action links (MAX-first) — фундамент + Sprint 2 actions."""

from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.secure_links.service import SecureActionLinkService
from sfrfr.secure_links.token import (
    PURPOSES,
    generate_raw_token,
    hash_token,
    token_prefix,
)
from sfrfr.secure_links.urls import public_secure_action_url, public_secure_pdf_url

__all__ = [
    "PURPOSES",
    "SecureActionLinkService",
    "SecureLinkDenied",
    "SecureLinksDisabled",
    "generate_raw_token",
    "hash_token",
    "public_secure_action_url",
    "public_secure_pdf_url",
    "token_prefix",
]
