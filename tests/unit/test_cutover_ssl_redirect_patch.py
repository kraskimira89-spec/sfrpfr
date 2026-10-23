"""Память регрессии: SSL-redirect патч cutover пишет реальные переводы строк."""

from __future__ import annotations

from pathlib import Path


def _patch_ssl_redirect(path: Path, target: str) -> None:
    """Зеркало python-блока из scripts/vps_cutover_proverkastaza.sh."""
    text = path.read_text(encoding="utf-8")
    snippet = (
        "\n    RewriteEngine On\n"
        f"    RewriteRule ^ https://{target}%{{REQUEST_URI}} [R=301,L]\n"
    )
    # Только правило для этого target — не любой RewriteRule в файле.
    if f"RewriteRule ^ https://{target}" in text:
        return
    idx = text.rfind("</VirtualHost>")
    assert idx >= 0
    path.write_text(text[:idx] + snippet + text[idx:], encoding="utf-8")


def test_ssl_redirect_patch_inserts_real_newlines_and_request_uri(tmp_path: Path) -> None:
    conf = tmp_path / "old-le-ssl.conf"
    conf.write_text(
        "<IfModule mod_ssl.c>\n"
        "<VirtualHost *:443>\n"
        "    ServerName example.old\n"
        "    SSLEngine on\n"
        "</VirtualHost>\n"
        "</IfModule>\n",
        encoding="utf-8",
    )
    _patch_ssl_redirect(conf, "proverkastaza.ru")
    out = conf.read_text(encoding="utf-8")
    assert "\\n" not in out
    assert "RewriteEngine On\n" in out
    assert "RewriteRule ^ https://proverkastaza.ru%{REQUEST_URI} [R=301,L]" in out
    assert out.index("RewriteEngine On") < out.index("</VirtualHost>")


def test_ssl_redirect_patch_other_rule_does_not_block_new_target(tmp_path: Path) -> None:
    """Чужой RewriteRule + упоминание URL target ≠ skip для нового target."""
    conf = tmp_path / "mixed-le-ssl.conf"
    conf.write_text(
        "<IfModule mod_ssl.c>\n"
        "<VirtualHost *:443>\n"
        "    ServerName api.example.old\n"
        "    # see also https://api.proverkastaza.ru\n"
        "    RewriteEngine On\n"
        "    RewriteRule ^ https://proverkastaza.ru%{REQUEST_URI} [R=301,L]\n"
        "</VirtualHost>\n"
        "</IfModule>\n",
        encoding="utf-8",
    )
    _patch_ssl_redirect(conf, "api.proverkastaza.ru")
    out = conf.read_text(encoding="utf-8")
    assert "RewriteRule ^ https://api.proverkastaza.ru%{REQUEST_URI} [R=301,L]" in out
    assert "RewriteRule ^ https://proverkastaza.ru%{REQUEST_URI}" in out


def test_ssl_redirect_patch_idempotent_for_same_target(tmp_path: Path) -> None:
    conf = tmp_path / "idempotent.conf"
    conf.write_text(
        "<VirtualHost *:443>\n"
        "    RewriteEngine On\n"
        "    RewriteRule ^ https://cabinet.proverkastaza.ru%{REQUEST_URI} [R=301,L]\n"
        "</VirtualHost>\n",
        encoding="utf-8",
    )
    before = conf.read_text(encoding="utf-8")
    _patch_ssl_redirect(conf, "cabinet.proverkastaza.ru")
    assert conf.read_text(encoding="utf-8") == before
