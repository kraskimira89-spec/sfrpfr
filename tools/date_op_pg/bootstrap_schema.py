"""Применить tools/date_op_pg/schema_minimal.sql к DATABASE_URL (local/test only)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg


def _psycopg_dsn(url: str) -> str:
    raw = (url or "").strip()
    if raw.startswith("postgresql+psycopg://"):
        return "postgresql://" + raw[len("postgresql+psycopg://") :]
    return raw


def _assert_local(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost"} and "test" not in host:
        raise SystemExit(
            f"refuse bootstrap on non-local host={host!r}; "
            "use 127.0.0.1 / localhost / *test*"
        )


def main() -> int:
    url = _psycopg_dsn(
        os.environ.get("DATABASE_URL")
        or "postgresql://sfrfr:sfrfr_test@127.0.0.1:15433/sfrfr_date_op_test"
    )
    _assert_local(url)
    schema = Path(__file__).with_name("schema_minimal.sql").read_text(encoding="utf-8")
    with psycopg.connect(url, connect_timeout=10) as conn:
        conn.execute(schema)
        conn.commit()
    print("schema_ok", urlparse(url).hostname, urlparse(url).port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
