"""Runtime probe: computed styles of Главная dropdown on production."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
LOG = Path(__file__).resolve().parents[1] / "debug-016b5f.log"
ENDPOINT = "http://127.0.0.1:7431/ingest/15b5aa1f-f97a-42c4-8de4-bc9cab7ebdc3"


def emit(hypothesis_id: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "016b5f",
        "runId": "runtime-probe",
        "hypothesisId": hypothesis_id,
        "location": "scripts/_debug_menu_runtime.py",
        "message": message,
        "data": data,
        "timestamp": __import__("time").time() * 1000,
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
    except Exception as exc:  # noqa: BLE001
        print("ingest_warn", type(exc).__name__, exc)
    print(hypothesis_id, message, json.dumps(data, ensure_ascii=False)[:500])


JS = r"""
() => {
  const dig = (el) => {
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {
      tag: el.tagName,
      className: el.className,
      bg: cs.backgroundColor,
      color: cs.color,
      borderTop: cs.borderTop,
      borderRight: cs.borderRight,
      borderBottom: cs.borderBottom,
      borderLeft: cs.borderLeft,
      boxShadow: cs.boxShadow,
      display: cs.display,
      visibility: cs.visibility,
      opacity: cs.opacity,
      zIndex: cs.zIndex,
    };
  };

  const customCss = document.getElementById('wp-custom-css');
  const cssText = customCss ? customCss.textContent || '' : '';
  const hasInsetRight = cssText.includes('inset -3px 0 0');
  const hasWhiteSub = cssText.includes('background: #ffffff !important');

  const desktop = document.querySelector('#ast-hf-menu-1');
  const tops = [...(desktop?.querySelectorAll(':scope > .menu-item') || [])].map((li) => {
    const a = li.querySelector(':scope > .menu-link');
    return {
      id: li.id,
      text: (a?.textContent || '').replace(/\s+/g, ' ').trim(),
      hasSub: !!li.querySelector(':scope > .sub-menu'),
      classes: li.className,
    };
  });

  const home = [...(desktop?.querySelectorAll(':scope > .menu-item') || [])].find((li) => {
    const t = (li.querySelector(':scope > .menu-link')?.textContent || '').replace(/\s+/g, ' ').trim();
    return t.startsWith('Главная');
  });

  let sub = home?.querySelector(':scope > .sub-menu') || null;
  // force open for measurement
  if (home && sub) {
    home.classList.add('ast-submenu-expanded', 'focus');
    sub.style.display = 'block';
    sub.style.visibility = 'visible';
    sub.style.opacity = '1';
    sub.style.pointerEvents = 'auto';
  }

  const firstItem = sub?.querySelector(':scope > .menu-item');
  const firstLink = firstItem?.querySelector(':scope > .menu-link');
  if (firstItem) firstItem.classList.add('focus');

  // matching rules for submenu background via CSSOM if possible
  let matched = [];
  try {
    if (sub) {
      for (const sheet of document.styleSheets) {
        let rules;
        try { rules = sheet.cssRules; } catch { continue; }
        if (!rules) continue;
        for (const rule of rules) {
          if (!rule.selectorText || !rule.style) continue;
          if (!String(rule.selectorText).includes('sub-menu')) continue;
          try {
            if (sub.matches(rule.selectorText.split(',')[0].trim()) ||
                String(rule.selectorText).includes('.sub-menu')) {
              const bg = rule.style.background || rule.style.backgroundColor;
              const bl = rule.style.borderLeft || rule.style.borderLeftWidth;
              const br = rule.style.borderRight || rule.style.borderRightWidth;
              const sh = rule.style.boxShadow;
              if (bg || bl || br || sh || rule.style.color) {
                matched.push({
                  sel: rule.selectorText.slice(0, 180),
                  bg, bl, br, sh,
                  color: rule.style.color,
                  importantBg: rule.style.getPropertyPriority('background') || rule.style.getPropertyPriority('background-color'),
                });
              }
            }
          } catch {}
        }
      }
    }
  } catch (e) {
    matched = [{ error: String(e) }];
  }

  return {
    hasCustomCss: !!customCss,
    hasInsetRight,
    hasWhiteSub,
    tops,
    homeFound: !!home,
    subFound: !!sub,
    sub: dig(sub),
    firstLink: dig(firstLink),
    firstLinkText: (firstLink?.textContent || '').replace(/\s+/g, ' ').trim(),
    parentLi: dig(home),
    matchedRulesSample: matched.slice(0, 25),
    matchedCount: matched.length,
    astColor0: getComputedStyle(document.documentElement).getPropertyValue('--ast-global-color-0').trim(),
    sfrfrInk: getComputedStyle(document.documentElement).getPropertyValue('--sfrfr-ink').trim(),
  };
}
"""


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("https://proverkastaza.ru/?nocache=dbg016b5f", wait_until="networkidle", timeout=60000)
        data = page.evaluate(JS)

        emit("H1", "menu structure tops", {"tops": data.get("tops"), "homeFound": data.get("homeFound"), "subFound": data.get("subFound")})
        emit("H2", "custom css markers present in DOM", {
            "hasCustomCss": data.get("hasCustomCss"),
            "hasInsetRight": data.get("hasInsetRight"),
            "hasWhiteSub": data.get("hasWhiteSub"),
        })
        emit("H3", "computed styles of Главная .sub-menu", {"sub": data.get("sub"), "astColor0": data.get("astColor0")})
        emit("H4", "computed styles of first submenu link", {
            "firstLink": data.get("firstLink"),
            "firstLinkText": data.get("firstLinkText"),
            "sfrfrInk": data.get("sfrfrInk"),
        })
        emit("H5", "cssom matched submenu rules sample", {
            "matchedCount": data.get("matchedCount"),
            "matchedRulesSample": data.get("matchedRulesSample"),
        })

        # hover first item and re-read
        if data.get("subFound"):
            page.hover("#ast-hf-menu-1 > .menu-item-has-children >> nth=0")
            page.wait_for_timeout(300)
            link = page.locator("#ast-hf-menu-1 > .menu-item-has-children >> nth=0 >> .sub-menu > .menu-item >> nth=0 > .menu-link")
            link.hover()
            page.wait_for_timeout(200)
            hover = page.evaluate(
                """() => {
                  const home = document.querySelector('#ast-hf-menu-1 > .menu-item-has-children');
                  const sub = home && home.querySelector(':scope > .sub-menu');
                  const link = sub && sub.querySelector(':scope > .menu-item > .menu-link');
                  if (!link) return null;
                  const cs = getComputedStyle(link);
                  const sc = sub ? getComputedStyle(sub) : null;
                  return {
                    linkBg: cs.backgroundColor,
                    linkColor: cs.color,
                    linkShadow: cs.boxShadow,
                    subBg: sc && sc.backgroundColor,
                    subBorderLeft: sc && sc.borderLeft,
                    subBorderRight: sc && sc.borderRight,
                    subBoxShadow: sc && sc.boxShadow,
                  };
                }"""
            )
            emit("H3", "hover computed styles", {"hover": hover})

        browser.close()


if __name__ == "__main__":
    main()
