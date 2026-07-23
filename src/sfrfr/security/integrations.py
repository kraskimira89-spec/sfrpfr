"""Проверки безопасности интеграций (ТЗ-06)."""

from __future__ import annotations

from pathlib import Path

# Signed URL TTL в секундах (portal).
SIGNED_URL_TTL_SECONDS = 60

PRIVATE_STORAGE_BUCKET = "pension-docs"


def assert_frontend_env_has_no_service_role(env_text: str) -> None:
    """Браузерные .env не должны содержать service_role."""
    for line in env_text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        key = raw.split("=", 1)[0].strip().upper()
        if "SERVICE_ROLE" in key:
            raise AssertionError(f"service_role must not appear in frontend env: {key}")
        if key.startswith("NEXT_PUBLIC_") and "SERVICE" in key:
            raise AssertionError(f"forbidden public secret-like key: {key}")


def check_cabinet_env_examples(repo_root: Path | None = None) -> list[str]:
    root = repo_root or Path(__file__).resolve().parents[3]
    errors: list[str] = []
    for rel in ("apps/cabinet/.env.example", "apps/admin/.env.example"):
        path = root / rel
        if not path.exists():
            continue
        try:
            assert_frontend_env_has_no_service_role(path.read_text(encoding="utf-8"))
        except AssertionError as exc:
            errors.append(f"{rel}: {exc}")
    return errors
