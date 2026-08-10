"""Runtime probe: why header/menu layout broke."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
LOG = Path(__file__).resolve().parents[1] / "debug-016b5f.log"


def emit(hid: str, msg: str, data: dict) -> None:
    payload = {
        "sessionId": "016b5f",
        "runId": "layout-break",
        "hypothesisId": hid,
        "location": "scripts/_debug_header_layout.py",
        "message": msg,
        "data": data,
        "timestamp": time.time() * 1000,
    }
    LOG.open("a", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(hid, msg)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])


JS = r"""
() => {
  const dig = (el) => {
    if (!el) return null;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      cls: (el.className || '').toString().slice(0, 140),
      w: Math.round(r.width),
      h: Math.round(r.height),
      x: Math.round(r.x),
      y: Math.round(r.y),
      display: cs.display,
      position: cs.position,
      flex: cs.flex,
      flexWrap: cs.flexWrap,
      whiteSpace: cs.whiteSpace,
      width: cs.width,
      maxWidth: cs.maxWidth,
      minWidth: cs.minWidth,
      overflow: cs.overflow,
      visibility: cs.visibility,
      opacity: cs.opacity,
    };
  };

  const tops = [...document.querySelectorAll('#ast-hf-menu-1 > .menu-item')].map((li) => {
    const a = li.querySelector(':scope > .menu-link');
    const sub = li.querySelector(':scope > .sub-menu');
    const r = li.getBoundingClientRect();
    const cs = getComputedStyle(li);
    let subInfo = null;
    if (sub) {
      const sc = getComputedStyle(sub);
      const sr = sub.getBoundingClientRect();
      subInfo = {
        display: sc.display,
        position: sc.position,
        visibility: sc.visibility,
        opacity: sc.opacity,
        w: Math.round(sr.width),
        h: Math.round(sr.height),
        x: Math.round(sr.x),
        y: Math.round(sr.y),
        items: [...sub.querySelectorAll(':scope > .menu-item > .menu-link')].map(
          (x) => (x.textContent || '').replace(/\s+/g, ' ').trim()
        ),
      };
    }
    return {
      text: ((a && a.textContent) || '').replace(/\s+/g, ' ').trim(),
      hasSub: !!sub,
      w: Math.round(r.width),
      h: Math.round(r.height),
      x: Math.round(r.x),
      y: Math.round(r.y),
      display: cs.display,
      position: cs.position,
      sub: subInfo,
    };
  });

  // Any submenu links that appear in the top header band (y < 120)
  const leaked = [...document.querySelectorAll('#ast-hf-menu-1 .sub-menu .menu-link')]
    .map((a) => {
      const r = a.getBoundingClientRect();
      const cs = getComputedStyle(a);
      return {
        text: (a.textContent || '').replace(/\s+/g, ' ').trim(),
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        visible: cs.visibility !== 'hidden' && cs.display !== 'none' && r.height > 0 && r.width > 0,
        color: cs.color,
      };
    })
    .filter((x) => x.visible && x.y < 140);

  const title = document.querySelector('.site-title');
  const identity = document.querySelector('.ast-site-identity, .site-branding');
  const logoImg = document.querySelector('.custom-logo, .custom-logo-link img');
  const menu = document.querySelector('#ast-hf-menu-1');
  const headerRow = document.querySelector('.ast-builder-grid-row, .ast-main-header-wrap, .site-header .ast-container');

  return {
    tops,
    leakedInHeaderBand: leaked,
    title: dig(title),
    titleText: title ? title.textContent.trim() : null,
    identity: dig(identity),
    logoImg: dig(logoImg),
    menu: dig(menu),
    headerRow: dig(headerRow),
    viewport: { w: innerWidth, h: innerHeight },
  };
}
"""


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.goto(
        "https://proverkastaza.ru/?nocache=layout2",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(1500)
    data = page.evaluate(JS)
    emit("L1", "top-level menu items", {"tops": data["tops"]})
    emit("L2", "leaked submenu links in header band", {"leaked": data["leakedInHeaderBand"]})
    emit(
        "L3",
        "logo/title/menu geometry",
        {
            "title": data["title"],
            "titleText": data["titleText"],
            "identity": data["identity"],
            "logoImg": data["logoImg"],
            "menu": data["menu"],
            "headerRow": data["headerRow"],
            "viewport": data["viewport"],
        },
    )
    page.screenshot(path=str(Path("scripts/_debug_header_break.png")), full_page=False)
    browser.close()
