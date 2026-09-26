import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import verify_prod_schema_drift as drift  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


class _FakeCursor:
    def __init__(self, log: list[str], conn: "_FakeConn") -> None:
        self._log = log
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        assert self._conn.read_only is True, "запрос до включения read_only"
        self._log.append(sql)

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self) -> None:
        self.read_only = False
        self.log: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return _FakeCursor(self.log, self)


def test_expected_covers_each_migration_file_once():
    versions = [m.version for m in drift.EXPECTED]
    assert len(versions) == len(set(versions)) == 16
    for m in drift.EXPECTED:
        files = list(MIGRATIONS_DIR.glob(f"{m.version}_*.sql"))
        assert len(files) == 1, m.version
        assert m.checks, m.version


def test_main_requires_database_url(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert drift.main() == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_main_is_read_only_and_hides_dsn(monkeypatch, capsys):
    dsn = "postgresql://user:s3cret@db.example:5433/postgres"
    conn = _FakeConn()
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setattr(drift.psycopg, "connect", lambda _dsn: conn)

    assert drift.main() == 1

    out = capsys.readouterr()
    assert conn.read_only is True
    assert conn.log
    write_words = ("insert ", "update ", "delete ", "alter ", "drop ", "create ", "grant ")
    assert not any(word in sql.lower() for sql in conn.log for word in write_words)
    assert "MISSING" in out.out
    assert "s3cret" not in out.out + out.err
    assert "db.example" not in out.out + out.err
