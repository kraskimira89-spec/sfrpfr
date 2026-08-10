"""Reproduce header crush at multiple widths; dump menu HTML structure."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
LOG = Path(__file__).resolve().parents[1] / "debug-016b5f.log"


def emit(hid: str, msg: str, data: dict) -> None:
    payload = {
        "sessionId": "016b5f",
        "runId": "layout-break-2",
        "hypothesisId": hid,
        "location": "scripts/_debug_header_layout2.py",
        "message": msg,
        "data": data,
        "timestamp": time.time() * 1000,
    }
    LOG.open("a", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(hid, msg, json.dumps(data, ensure_ascii=False)[:900])


# HTML structure via urllib
req = urllib.request.Request(
    "https://proverkastaza.ru/?nocache=layout3",
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
import re

m = re.search(r'id="ast-hf-menu-1"[^>]*>(.*?)</ul>\s*</div>\s*</nav>', html, re.S)
block = m.group(1) if m else ""
# top-level only: count direct li by tracking depth roughly via regex of menu-item ids at start of li
tops = re.findall(
    r'<li[^>]*id="(menu-item-\d+)"[^>]*class="([^"]*)"[^>]*>\s*<a[^>]*class="menu-link"[^>]*>(.*?)</a>',
    block,
    re.S,
)


def strip(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


# Better: parse only depth-0 by removing nested ul first
def top_level_items(ul_inner: str):
    items = []
    i = 0
    while True:
        li = ul_inner.find("<li", i)
        if li < 0:
            break
        # find matching close for this li with nesting
        pos = li
        depth = 0
        end = None
        while pos < len(ul_inner):
            next_li = ul_inner.find("<li", pos + 1)
            next_close = ul_inner.find("</li>", pos + 1)
            if next_close < 0:
                break
            if next_li >= 0 and next_li < next_close:
                depth += 1
                pos = next_li
            else:
                if depth == 0:
                    end = next_close + 5
                    break
                depth -= 1
                pos = next_close
        if end is None:
            break
        chunk = ul_inner[li:end]
        mid = re.search(r'id="(menu-item-\d+)"', chunk)
        title_m = re.search(r'class="menu-link"[^>]*>(.*?)</a>', chunk, re.S)
        has_sub = 'class="sub-menu"' in chunk
        items.append(
            {
                "id": mid.group(1) if mid else "",
                "text": strip(title_m.group(1)) if title_m else "",
                "hasSub": has_sub,
            }
        )
        i = end
    return items


tops_parsed = top_level_items(block)
emit("L4", "HTML top-level menu structure", {"tops": tops_parsed, "count": len(tops_parsed)})

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for width in (1440, 1280, 1200, 1100, 1024):
        page = browser.new_page(
            viewport={"width": width, "height": 900},
            device_scale_factor=1,
        )
        page.goto(
            f"https://proverkastaza.ru/?nocache=w{width}",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(800)
        data = page.evaluate(
            """() => {
              const title = document.querySelector('.site-title');
              const identity = document.querySelector('.ast-site-identity, .site-branding');
              const menu = document.querySelector('#ast-hf-menu-1');
              const tr = title ? title.getBoundingClientRect() : null;
              const ir = identity ? identity.getBoundingClientRect() : null;
              const mr = menu ? menu.getBoundingClientRect() : null;
              const tops = [...document.querySelectorAll('#ast-hf-menu-1 > .menu-item')].map(li => {
                const a = li.querySelector(':scope > .menu-link');
                return ((a&&a.textContent)||'').replace(/\\s+/g,' ').trim();
              });
              const titleCs = title ? getComputedStyle(title) : null;
              return {
                titleW: tr && Math.round(tr.width),
                titleH: tr && Math.round(tr.height),
                identityW: ir && Math.round(ir.width),
                identityH: ir && Math.round(ir.height),
                menuW: mr && Math.round(mr.width),
                menuH: mr && Math.round(mr.height),
                titleWhiteSpace: titleCs && titleCs.whiteSpace,
                titleWordBreak: titleCs && titleCs.wordBreak,
                tops,
                crushed: !!(tr && tr.width < 80 && tr.height > 60),
              };
            }"""
        )
        emit("L5", f"viewport {width}", data)
        if data.get("crushed") or (data.get("titleH") or 0) > 50:
            page.screenshot(path=f"scripts/_debug_header_w{width}.png")
        page.close()

    # zoom-like: 1360 CSS px with scale 1.25 via viewport
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    page.goto("https://proverkastaza.ru/?nocache=zoom", wait_until="domcontentloaded", timeout=60000)
    page.evaluate("document.body.style.zoom='125%'")
    page.wait_for_timeout(500)
    data = page.evaluate(
        """() => {
          const title = document.querySelector('.site-title');
          const r = title.getBoundingClientRect();
          const tops = [...document.querySelectorAll('#ast-hf-menu-1 > .menu-item')].map(li => {
            const a = li.querySelector(':scope > .menu-link');
            return ((a&&a.textContent)||'').replace(/\\s+/g,' ').trim();
          });
          return { titleW: Math.round(r.width), titleH: Math.round(r.height), tops,
            crushed: r.width < 80 && r.height > 60 };
        }"""
    )
    emit("L6", "zoom 125%", data)
    page.screenshot(path="scripts/_debug_header_zoom125.png")
    browser.close()
