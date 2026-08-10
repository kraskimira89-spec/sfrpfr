"""Post-fix: hover bg must not be greenish #f3f7f4."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
LOG = Path(__file__).resolve().parents[1] / "debug-016b5f.log"
ENDPOINT = "http://127.0.0.1:7431/ingest/15b5aa1f-f97a-42c4-8de4-bc9cab7ebdc3"


def emit(message: str, data: dict) -> None:
    payload = {
        "sessionId": "016b5f",
        "runId": "post-fix",
        "hypothesisId": "H-GREEN-BG",
        "location": "scripts/_debug_menu_verify_v3.py",
        "message": message,
        "data": data,
        "timestamp": time.time() * 1000,
    }
    line = json.dumps(payload, ensure_ascii=False)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        req = urllib.request.Request(
            ENDPOINT,
            data=line.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Debug-Session-Id": "016b5f",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass
    print(message, json.dumps(data, ensure_ascii=False)[:500])


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(
        "https://proverkastaza.ru/?nocache=v3verify",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(1200)
    css_ok = page.evaluate(
        """() => {
          const t = document.getElementById('wp-custom-css')?.textContent || '';
          return {
            hasV3: t.includes('sfrfr-nav-dropdown-v3'),
            hasGreenHoverBg: t.includes('background: #f3f7f4 !important'),
          };
        }"""
    )
    emit("css markers", css_ok)
    page.locator("#ast-hf-menu-1 > .menu-item-has-children").first.hover()
    page.wait_for_timeout(400)
    page.locator(
        "#ast-hf-menu-1 > .menu-item-has-children >> nth=0 >> .sub-menu > .menu-item >> nth=1 > .menu-link"
    ).hover(timeout=10000)
    page.wait_for_timeout(200)
    hover = page.evaluate(
        """() => {
          const home = document.querySelector('#ast-hf-menu-1 > .menu-item-has-children');
          const sub = home?.querySelector(':scope > .sub-menu');
          const links = [...(sub?.querySelectorAll(':scope > .menu-item > .menu-link') || [])];
          const hovered = links.find((a) => {
            const cs = getComputedStyle(a);
            return cs.boxShadow.includes('46, 125, 91') || cs.boxShadow.includes('-3px');
          }) || links[1] || links[0];
          const cs = hovered ? getComputedStyle(hovered) : null;
          const sc = sub ? getComputedStyle(sub) : null;
          return {
            linkText: (hovered?.textContent || '').replace(/\\s+/g, ' ').trim(),
            linkBg: cs && cs.backgroundColor,
            linkShadow: cs && cs.boxShadow,
            subBg: sc && sc.backgroundColor,
            isGreenishHover:
              cs &&
              (cs.backgroundColor === 'rgb(243, 247, 244)' ||
                cs.backgroundColor === 'rgba(243, 247, 244, 1)'),
          };
        }"""
    )
    emit("hover computed", hover)
    browser.close()
