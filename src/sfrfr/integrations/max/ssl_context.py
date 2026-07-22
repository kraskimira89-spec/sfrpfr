"""TLS для MAX API: certifi + корневые сертификаты Минцифры."""

from __future__ import annotations

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

    out_dir = Path("/tmp") if Path("/tmp").is_dir() else Path.cwd()
    out = out_dir / "sfrfr-ca-bundle.pem"
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return str(out)
