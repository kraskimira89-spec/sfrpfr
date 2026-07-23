"""TLS для MAX API: certifi + корневые сертификаты Минцифры."""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

import certifi

# src/sfrfr/integrations/max/ssl_context.py -> корень репозитория
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CANDIDATE_DIRS = (
    _REPO_ROOT / "certs",
    Path("/opt/sfrfr/certs"),
    Path.cwd() / "certs",
)


def _bundle_paths() -> list[Path]:
    """Пишем в пути, доступные текущему пользователю сервиса."""
    uid = getattr(os, "getuid", lambda: 0)()
    return [
        Path("/opt/sfrfr/var") / "sfrfr-ca-bundle.pem",
        Path(tempfile.gettempdir()) / f"sfrfr-ca-bundle-{uid}.pem",
        Path.cwd() / "sfrfr-ca-bundle.pem",
    ]


@lru_cache
def max_ssl_verify() -> str:
    """
    Путь к CA-бандлу: Mozilla (certifi) + Russian Trusted Root/Sub CA.
    Без сертификатов Минцифры https://platform-api2.max.ru даёт CERTIFICATE_VERIFY_FAILED.
    """
    parts: list[str] = [Path(certifi.where()).read_text(encoding="utf-8")]
    for directory in _CANDIDATE_DIRS:
        root = directory / "russian_trusted_root_ca.pem"
        sub = directory / "russian_trusted_sub_ca.pem"
        if root.is_file() or sub.is_file():
            if root.is_file():
                parts.append(root.read_text(encoding="utf-8"))
            if sub.is_file():
                parts.append(sub.read_text(encoding="utf-8"))
            break

    content = "\n".join(parts) + "\n"
    last_error: Exception | None = None
    for out in _bundle_paths():
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")
            return str(out)
        except OSError as exc:
            last_error = exc
            continue
    raise PermissionError(
        f"cannot write MAX CA bundle; last error: {last_error}"
    ) from last_error
