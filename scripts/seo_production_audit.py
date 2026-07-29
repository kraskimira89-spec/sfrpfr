#!/usr/bin/env python3
"""Проверка технического SEO публичной WordPress-витрины.

Без секретов и сторонних зависимостей:
  python scripts/seo_production_audit.py
  python scripts/seo_production_audit.py --base-url https://proverkastaza.ru --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
USER_AGENT = "SFRFR-SEO-Audit/1.0 (+https://proverkastaza.ru/)"


@dataclass(frozen=True)
class PageResult:
    url: str
    status: int
    issues: tuple[str, ...]


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    if path != "/" and not path.endswith("/"):
        path += "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def fetch(url: str, *, attempts: int = 2, timeout: float = 20.0) -> tuple[int, str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5)
    raise RuntimeError(f"GET {url}: {last_error}")


def extract_attr_tag(html: str, *, tag: str, attr: str, value: str) -> list[str]:
    pattern = rf"<{tag}\b(?=[^>]*\b{attr}=[\"']{re.escape(value)}[\"'])[^>]*>"
    return re.findall(pattern, html, flags=re.IGNORECASE | re.DOTALL)


def extract_attr(tag: str, attr: str) -> str:
    match = re.search(rf"\b{attr}=[\"']([^\"']+)[\"']", tag, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def audit_html(url: str, status: int, html: str) -> PageResult:
    issues: list[str] = []
    if status != 200:
        issues.append(f"http:{status}")

    descriptions = extract_attr_tag(html, tag="meta", attr="name", value="description")
    if len(descriptions) != 1:
        issues.append(f"description:{len(descriptions)}")
    elif not extract_attr(descriptions[0], "content"):
        issues.append("description:empty")

    canonicals = extract_attr_tag(html, tag="link", attr="rel", value="canonical")
    if len(canonicals) != 1:
        issues.append(f"canonical:{len(canonicals)}")
    else:
        canonical = extract_attr(canonicals[0], "href")
        if normalize_url(canonical) != normalize_url(url):
            issues.append(f"canonical:mismatch:{canonical}")

    schemas = re.findall(
        r"<script\b(?=[^>]*\btype=[\"']application/ld\+json[\"'])[^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if len(schemas) != 1:
        issues.append(f"jsonld:{len(schemas)}")
    else:
        try:
            payload = json.loads(schemas[0])
            if payload.get("@context") != "https://schema.org" or not payload.get("@graph"):
                issues.append("jsonld:shape")
        except (json.JSONDecodeError, AttributeError):
            issues.append("jsonld:invalid")

    for prop in ("og:title", "og:description", "og:url"):
        tags = extract_attr_tag(html, tag="meta", attr="property", value=prop)
        if len(tags) != 1 or not extract_attr(tags[0], "content"):
            issues.append(f"{prop}:{len(tags)}")

    h1_count = len(re.findall(r"<h1\b[^>]*>", html, flags=re.IGNORECASE))
    if h1_count != 1:
        issues.append(f"h1:{h1_count}")

    robots = extract_attr_tag(html, tag="meta", attr="name", value="robots")
    has_noindex = any("noindex" in extract_attr(tag, "content").lower() for tag in robots)
    if has_noindex:
        # Тонкие/служебные URL с noindex не считаем дефектом индексации.
        # Остаются только проблемы доступности страницы.
        hard = [i for i in issues if i.startswith("http:") or i.startswith("fetch:")]
        return PageResult(url=url, status=status, issues=tuple(hard))

    return PageResult(url=url, status=status, issues=tuple(issues))


def parse_sitemap(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    return [
        (node.text or "").strip()
        for node in root.findall(".//sm:loc", SITEMAP_NS)
        if (node.text or "").strip()
    ]


def collect_urls(sitemap_url: str) -> list[str]:
    status, body = fetch(sitemap_url)
    if status != 200:
        raise RuntimeError(f"sitemap HTTP {status}: {sitemap_url}")
    children = parse_sitemap(body)
    urls: list[str] = []
    for child in children:
        child_status, child_body = fetch(child)
        if child_status != 200:
            raise RuntimeError(f"child sitemap HTTP {child_status}: {child}")
        urls.extend(parse_sitemap(child_body))
    return list(dict.fromkeys(urls))


def audit_page(url: str) -> PageResult:
    try:
        status, html = fetch(url)
        return audit_html(url, status, html)
    except Exception as exc:  # noqa: BLE001 - audit must report every URL
        return PageResult(url=url, status=0, issues=(f"fetch:{exc}",))


def audit_app_noindex(base_url: str) -> PageResult:
    url = urljoin(base_url.rstrip("/") + "/", "app/")
    try:
        status, html = fetch(url)
    except Exception as exc:  # noqa: BLE001
        return PageResult(url=url, status=0, issues=(f"fetch:{exc}",))
    issues: list[str] = []
    if status != 200:
        issues.append(f"http:{status}")
    robots = extract_attr_tag(html, tag="meta", attr="name", value="robots")
    content = " ".join(extract_attr(tag, "content").lower() for tag in robots)
    for directive in ("noindex", "nofollow", "noarchive"):
        if directive not in content:
            issues.append(f"robots:missing:{directive}")
    return PageResult(url=url, status=status, issues=tuple(issues))


def run(base_url: str, workers: int) -> dict[str, Any]:
    sitemap_url = urljoin(base_url.rstrip("/") + "/", "wp-sitemap.xml")
    urls = collect_urls(sitemap_url)
    results: list[PageResult] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(audit_page, url): url for url in urls}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item.url)
    app = audit_app_noindex(base_url)
    failed = [item for item in results if item.issues]
    if app.issues:
        failed.append(app)
    return {
        "base_url": base_url.rstrip("/"),
        "sitemap_url": sitemap_url,
        "pages": len(results),
        "passed": len(results) - sum(bool(item.issues) for item in results),
        "failed": len(failed),
        "results": [asdict(item) for item in failed],
        "app": asdict(app),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://proverkastaza.ru")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        report = run(args.base_url, args.workers)
    except Exception as exc:  # noqa: BLE001
        print(f"SEO AUDIT ERROR: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"SEO audit: pages={report['pages']} passed={report['passed']} "
            f"failed={report['failed']} sitemap={report['sitemap_url']}"
        )
        for result in report["results"]:
            print(f"FAIL {result['url']}: {', '.join(result['issues'])}")
        if not report["app"]["issues"]:
            print(f"OK app noindex: {report['app']['url']}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
