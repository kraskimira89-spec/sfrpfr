/**
 * Headless screenshot приёмки PR #284: viewport 1440 и 390.
 * Запуск: node tools/pr284-capture-route-preview.mjs [baseUrl]
 */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const base = process.argv[2] || "http://localhost:3011";
const outDir = path.resolve("docs/history/assets/pr284-route-preview");

async function measure(page) {
  return page.evaluate(() => {
    const layout = document.querySelector(".cabinet-case-layout");
    const main = document.querySelector(".cabinet-case-main");
    const chat = document.querySelector(".client-chat-panel");
    const input = document.querySelector("#case-chat-input");
    const m = main?.getBoundingClientRect();
    const c = chat?.getBoundingClientRect();
    return {
      vw: window.innerWidth,
      vh: window.innerHeight,
      layout: layout?.getAttribute("data-layout") || null,
      grid: layout ? getComputedStyle(layout).gridTemplateColumns : null,
      sideBySide: !!(m && c && c.left >= m.right - 8),
      stacked: !!(m && c && c.top >= m.bottom - 8),
      hasChatTitle: !!document.querySelector("#case-chat h2"),
      hasComposer: !!input,
      helpHref: document.querySelector('a[href="#case-chat-input"]')?.getAttribute("href") || null,
      chatLeft: c?.left ?? null,
      mainRight: m?.right ?? null,
    };
  });
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const report = [];

  {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    await page.goto(`${base}/dev/route-preview?s=upload`, { waitUntil: "networkidle" });
    await page.waitForSelector(".cabinet-case-layout");
    await page.waitForSelector(".client-chat-panel");
    await page.waitForTimeout(400);
    const m = await measure(page);
    report.push({ shot: "acceptance-desktop-1440.png", ...m });
    if (!m.sideBySide || !m.hasComposer) {
      throw new Error(`Desktop layout fail: ${JSON.stringify(m)}`);
    }
    // Проверка помощи → тот же чат
    await page.click('a[href="#case-chat-input"]');
    await page.waitForTimeout(200);
    const focused = await page.evaluate(() => document.activeElement?.id || document.activeElement?.tagName);
    report.push({ helpFocus: focused });
    await page.screenshot({
      path: path.join(outDir, "acceptance-desktop-1440.png"),
      fullPage: false,
    });
    await context.close();
  }

  {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });
    const page = await context.newPage();
    await page.goto(`${base}/dev/route-preview?s=upload`, { waitUntil: "networkidle" });
    await page.waitForSelector(".cabinet-case-layout");
    await page.waitForTimeout(400);
    const m = await measure(page);
    report.push({ shot: "acceptance-mobile-390.png", ...m });
    if (!m.stacked || m.sideBySide) {
      throw new Error(`Mobile layout fail: ${JSON.stringify(m)}`);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(outDir, "acceptance-mobile-390.png"),
      fullPage: false,
    });

    // Кнопка «Чат» (как в кабинете) → #case-chat
    const chatBtn = page.locator("a.case-chat-mobile-open");
    await chatBtn.waitFor({ state: "visible" });
    await chatBtn.click();
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(outDir, "acceptance-mobile-390-chat-focus.png"),
      fullPage: false,
    });
    const after = await page.evaluate(() => {
      const chat = document.querySelector("#case-chat");
      const input = document.querySelector("#case-chat-input");
      const r = chat?.getBoundingClientRect();
      return {
        hash: location.hash,
        chatInView: !!(r && r.top < window.innerHeight && r.bottom > 0),
        inputId: input?.id || null,
      };
    });
    report.push({ mobileChatJump: after });
    if (!after.chatInView) {
      throw new Error(`Mobile chat jump fail: ${JSON.stringify(after)}`);
    }
    await context.close();
  }

  await writeFile(path.join(outDir, "acceptance-measure.json"), JSON.stringify(report, null, 2), "utf8");
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
