"""Screenshot + hover styles for Главная dropdown."""
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
OUT = Path(__file__).resolve().parents[1] / "scripts" / "_debug_dropdown_glavnaya.png"


def emit(hypothesis_id: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "016b5f",
        "runId": "runtime-probe-2",
        "hypothesisId": hypothesis_id,
        "location": "scripts/_debug_menu_runtime2.py",
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
    except Exception as exc:  # noqa: BLE001
        print("ingest_warn", type(exc).__name__)
    print(hypothesis_id, message, json.dumps(data, ensure_ascii=False)[:700])


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(
        "https://proverkastaza.ru/?nocache=dbg016b5f2",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(1500)

    hover = page.evaluate(
        """() => {
          const home = [...document.querySelectorAll('#ast-hf-menu-1 > .menu-item')].find(li =>
            (li.querySelector(':scope > .menu-link')?.textContent || '').includes('Главная')
          );
          if (!home) return { error: 'no home' };
          const sub = home.querySelector(':scope > .sub-menu');
          if (!sub) return { error: 'no sub' };
          home.classList.add('focus', 'ast-submenu-expanded');
          home.setAttribute('aria-expanded', 'true');
          // Astra often toggles via .ast-desktop .menu-item.focus
          sub.removeAttribute('style');
          const csBefore = getComputedStyle(sub);
          // Force open like Astra desktop
          sub.style.setProperty('display', 'block', 'important');
          sub.style.setProperty('visibility', 'visible', 'important');
          sub.style.setProperty('opacity', '1', 'important');
          sub.style.setProperty('pointer-events', 'auto', 'important');
          [...sub.querySelectorAll('.menu-link')].forEach((a) => {
            a.style.setProperty('visibility', 'visible', 'important');
          });
          const firstLi = sub.querySelector(':scope > .menu-item');
          const firstLink = firstLi?.querySelector(':scope > .menu-link');
          firstLi?.classList.add('focus');
          // synthesize hover
          firstLi?.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
          firstLink?.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
          const csSub = getComputedStyle(sub);
          const csLink = firstLink ? getComputedStyle(firstLink) : null;
          const arrow = firstLink?.querySelector('.ast-icon, .icon-arrow, svg');
          const csArrow = arrow ? getComputedStyle(arrow) : null;
          return {
            subBg: csSub.backgroundColor,
            subBorderLeft: csSub.borderLeft,
            subBorderRight: csSub.borderRight,
            subShadow: csSub.boxShadow,
            linkBg: csLink && csLink.backgroundColor,
            linkColor: csLink && csLink.color,
            linkShadow: csLink && csLink.boxShadow,
            linkVisibility: csLink && csLink.visibility,
            hasArrow: !!arrow,
            arrowDisplay: csArrow && csArrow.display,
            arrowColor: csArrow && csArrow.color,
            beforeDisplay: csBefore.display,
            beforeVisibility: csBefore.visibility,
          };
        }"""
    )
    emit("H3", "forced-open + pseudo-hover styles", {"hover": hover})

    # also native hover on top item
    page.locator("#ast-hf-menu-1 > .menu-item-has-children").first.hover()
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT), full_page=False)
    emit("H6", "screenshot saved", {"path": str(OUT)})

    # Read styles after native hover
    native = page.evaluate(
        """() => {
          const home = document.querySelector('#ast-hf-menu-1 > .menu-item-has-children');
          const sub = home && home.querySelector(':scope > .sub-menu');
          if (!sub) return null;
          const link = sub.querySelector('.menu-item > .menu-link');
          const cs = getComputedStyle(sub);
          const cl = link ? getComputedStyle(link) : null;
          return {
            subDisplay: cs.display,
            subVisibility: cs.visibility,
            subBg: cs.backgroundColor,
            subBorderLeft: cs.borderLeft,
            subBorderRight: cs.borderRight,
            subShadow: cs.boxShadow,
            linkBg: cl && cl.backgroundColor,
            linkColor: cl && cl.color,
            linkShadow: cl && cl.boxShadow,
            homeClasses: home.className,
          };
        }"""
    )
    emit("H3", "native hover open styles", {"native": native})
    browser.close()
