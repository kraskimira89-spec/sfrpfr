#!/usr/bin/env python3
"""Playwright: согласие на статистические cookies vs внутренняя статистика.

Проверяет:
  - до выбора нет mc.yandex.ru;
  - «Разрешить» → tag.js/watch;
  - «Отказаться» → mc.yandex.ru не грузится;
  - серверный page_view не требует Метрики (косвенно: сайт отвечает 200).
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

URL = "https://proverkastaza.ru/"


def metrika_hits(urls: list[str]) -> list[str]:
    return [u for u in urls if "mc.yandex" in u and ("tag.js" in u or "/watch/" in u)]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # --- allow ---
        ctx1 = browser.new_context()
        page1 = ctx1.new_page()
        hits1: list[str] = []
        page1.on("request", lambda r: hits1.append(r.url))
        page1.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page1.wait_for_timeout(2000)
        if metrika_hits(hits1):
            print("FAIL: Metrika before consent (allow path)")
            return 1
        print("OK: no Metrika before consent")
        # тихий баннер с задержкой ~2.5с
        page1.locator("#sfrfr-metrika-consent.sfrfr-mc-visible").wait_for(state="visible", timeout=8000)
        page1.locator('[data-sfrfr-metrika-consent="1"]').click()
        page1.wait_for_timeout(3500)
        if not metrika_hits(hits1):
            print("FAIL: Metrika not loaded after Allow")
            return 1
        print("OK: Metrika after Allow")

        # повторный визит с тем же storage — баннер не должен появиться
        page1.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page1.wait_for_timeout(3500)
        visible = page1.locator("#sfrfr-metrika-consent.sfrfr-mc-visible").count()
        if visible:
            print("FAIL: banner shown again after choice")
            return 1
        print("OK: banner does not reappear")

        # --- deny ---
        ctx2 = browser.new_context()
        page2 = ctx2.new_page()
        hits2: list[str] = []
        page2.on("request", lambda r: hits2.append(r.url))
        page2.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page2.locator("#sfrfr-metrika-consent.sfrfr-mc-visible").wait_for(state="visible", timeout=8000)
        page2.locator('[data-sfrfr-metrika-consent="0"]').click()
        page2.wait_for_timeout(3000)
        if metrika_hits(hits2):
            print("FAIL: Metrika loaded after Deny")
            for u in metrika_hits(hits2)[:5]:
                print(" ", u[:160])
            return 1
        print("OK: Deny blocks Metrika")

        page2.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page2.wait_for_timeout(3500)
        if page2.locator("#sfrfr-metrika-consent.sfrfr-mc-visible").count():
            print("FAIL: banner reappears after deny")
            return 1
        print("OK: deny choice sticky (no second banner)")

        browser.close()
        print("DONE dual consent scenarios")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
