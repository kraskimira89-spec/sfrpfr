#!/usr/bin/env python3
"""Live-проверки сайта и автоисправления по кодам диагностики Вебмастера."""
from __future__ import annotations

import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://proverkastaza.ru"
CYRILLIC = re.compile(r"[\u0400-\u04FF]")

# Коды, которые можно чинить кодом/деплоем (не UI-only).
AUTO_FIX_CODES = frozenset(
    {
        "DISALLOWED_IN_ROBOTS",
        "ERROR_IN_ROBOTS_TXT",
        "NO_ROBOTS_TXT",
        "NO_SITEMAPS",
        "ERRORS_IN_SITEMAPS",
        "NO_SITEMAP_MODIFICATIONS",
        "FAVICON_PROBLEM",
        "MAIN_PAGE_ERROR",
        "SSL_CERTIFICATE_ERROR",
        "DOCUMENTS_MISSING_TITLE",
        "DOCUMENTS_MISSING_DESCRIPTION",
        "SOFT_404",
    }
)

UI_ONLY_CODES = frozenset(
    {
        "NO_REGIONS",
        "NOT_IN_SPRAV",
        "NO_METRIKA_COUNTER_CRAWL_ENABLED",
        "NO_METRIKA_COUNTER_BINDING",
        "BAD_ADVERTISEMENT",
        "TOO_MANY_PAGE_DUPLICATES",
        "THREATS",
        "DNS_ERROR",
        "SLOW_AVG_RESPONSE_TIME",
    }
)


def _http_label(status: int) -> str:
    """Человекочитаемый код ответа; 0 = сетевой/read timeout после ретраев."""
    if status == 0:
        return "timeout"
    return str(status)


def _is_retryable_timeout(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return True
        if isinstance(reason, OSError):
            # WinError 10060 / errno ETIMEDOUT и т.п.
            if getattr(reason, "winerror", None) == 10060:
                return True
            if getattr(reason, "errno", None) in {60, 110, 10060}:
                return True
        msg = str(reason).lower()
        if "timed out" in msg or "timeout" in msg:
            return True
    return False


def _fetch(url: str, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, method=method)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.status, headers, resp.read()
        except urllib.error.HTTPError as e:
            headers = {k.lower(): v for k, v in e.headers.items()}
            return e.code, headers, e.read()
        except (TimeoutError, urllib.error.URLError) as e:
            if _is_retryable_timeout(e) and attempt == 0:
                continue
            if _is_retryable_timeout(e):
                return 0, {}, b""
            raise
    return 0, {}, b""


def live_probe_issues() -> list[str]:
    issues: list[str] = []
    status, _, body = _fetch(f"{SITE}/robots.txt")
    text = body.decode("utf-8", errors="replace")
    if status == 0:
        # Локальная сеть/DNS часто режет сайт; дальше только тратим минуты.
        issues.append(f"robots.txt HTTP {_http_label(status)}")
        issues.append("further live probes skipped after network timeout")
        return issues
    if status != 200:
        issues.append(f"robots.txt HTTP {_http_label(status)}")
    elif CYRILLIC.search(text):
        issues.append("robots.txt contains Cyrillic")
    elif "Sitemap:" not in text:
        issues.append("robots.txt missing Sitemap directive")
    elif "Disallow: /" in text.splitlines() and "Disallow: /wp-admin/" not in text:
        issues.append("robots.txt blocks entire site")

    status, _, _ = _fetch(f"{SITE}/wp-sitemap.xml")
    if status != 200:
        issues.append(f"wp-sitemap.xml HTTP {_http_label(status)}")

    status, _, _ = _fetch(SITE)
    if status != 200:
        issues.append(f"homepage HTTP {_http_label(status)}")

    for path in ("/favicon.ico", "/favicon.svg", "/favicon-120.png"):
        status, headers, body = _fetch(f"{SITE}{path}")
        ctype = headers.get("content-type", "")
        if status != 200:
            issues.append(f"{path} HTTP {_http_label(status)}")
        elif "text/html" in ctype and len(body) > 0 and b"<html" in body[:500].lower():
            issues.append(f"{path} returns HTML instead of image")

    return issues


def run_ensure_site() -> str:
    script = ROOT / "scripts/yandex_webmaster_ensure_site.py"
    if not script.is_file():
        return "SKIP ensure_site: script missing"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode == 0:
        return "OK ensure_site"
    return f"WARN ensure_site exit {proc.returncode}: {proc.stderr[-400:]}"


def run_vps_ssh() -> str:
    host = __import__("os").environ.get("VPS_HOST", "91.229.11.147")
    user = __import__("os").environ.get("VPS_USER", "root")
    key = __import__("os").environ.get("VPS_SSH_KEY_PATH", "")
    port = __import__("os").environ.get("VPS_PORT", "22")
    cmd = ["ssh", "-o", "BatchMode=yes", "-p", port]
    if key:
        cmd.extend(["-i", key])
    cmd.append(f"{user}@{host}")
    cmd.append("bash /opt/sfrfr/scripts/vps_webmaster_remediate.sh")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    tail = (proc.stdout + proc.stderr)[-800:]
    if proc.returncode == 0:
        return f"OK vps_ssh remediate\n{tail}"
    return f"FAIL vps_ssh exit {proc.returncode}\n{tail}"


def remediate(
    apex_codes: list[str],
    *,
    ssh: bool = False,
) -> list[str]:
    """Вернуть журнал действий."""
    log: list[str] = []
    live = live_probe_issues()
    if live:
        log.append("live_probe: " + "; ".join(live))

    ui_blocked = [c for c in apex_codes if c in UI_ONLY_CODES]
    if ui_blocked:
        log.append("UI_ONLY (owner): " + ", ".join(ui_blocked))

    auto_codes = [c for c in apex_codes if c in AUTO_FIX_CODES]
    if auto_codes:
        log.append("api_codes: " + ", ".join(auto_codes))

    log.append(run_ensure_site())

    if ssh:
        log.append(run_vps_ssh())
    elif live or auto_codes:
        log.append("HINT: bash scripts/vps_webmaster_remediate.sh (or --ssh)")

    after = live_probe_issues()
    if after:
        log.append("after_probe STILL: " + "; ".join(after))
    else:
        log.append("after_probe: OK")

    return log
