from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
LOG = Path(__file__).resolve().parents[1] / "debug-016b5f.log"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    page.goto(
        "https://proverkastaza.ru/?nocache=layoutfix",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(1000)
    page.evaluate("document.body.style.zoom='125%'")
    page.wait_for_timeout(400)
    data = page.evaluate(
        """() => {
          const title = document.querySelector('.site-title');
          const r = title.getBoundingClientRect();
          const cs = getComputedStyle(title);
          const id = document.querySelector('.ast-site-identity');
          const ir = id.getBoundingClientRect();
          const css = document.getElementById('wp-custom-css')?.textContent || '';
          return {
            hasHeaderV1: css.includes('sfrfr-header-layout-v1'),
            titleW: Math.round(r.width),
            titleH: Math.round(r.height),
            identityW: Math.round(ir.width),
            identityH: Math.round(ir.height),
            whiteSpace: cs.whiteSpace,
            flexShrink: getComputedStyle(id).flexShrink,
            crushed: r.width < 80 && r.height > 60,
            tops: [...document.querySelectorAll('#ast-hf-menu-1 > .menu-item')].map((li) =>
              ((li.querySelector(':scope > .menu-link') || {}).textContent || '')
                .replace(/\\s+/g, ' ')
                .trim()
            ),
          };
        }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))
    LOG.open("a", encoding="utf-8").write(
        json.dumps(
            {
                "sessionId": "016b5f",
                "runId": "post-fix",
                "hypothesisId": "L6",
                "message": "zoom125 after fix",
                "data": data,
                "timestamp": time.time() * 1000,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    page.screenshot(path="scripts/_debug_header_zoom125_after.png")
    browser.close()
