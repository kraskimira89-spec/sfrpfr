/**
 * Приёмка 5 сценариев ТЗ на React-preview (не live user).
 * node tools/pr284-capture-scenarios.mjs [baseUrl]
 */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const base = process.argv[2] || "http://localhost:3011";
const outDir = path.resolve("docs/history/assets/pr284-route-preview");

/** Пять сценариев из ТЗ §7 + доп. CTA-пакет из review. */
const SCENARIOS = [
  {
    id: "consent",
    tz: 1,
    title: "Новый клиент — первый шаг",
    assert: async (page) => {
      const t = await page.textContent("body");
      const primary = (
        await page.getByRole("button", { name: /согласие/i }).first().textContent()
      )?.trim();
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      await page.getByRole("button", { name: "Вызвать handler сценария" }).click();
      await page.waitForTimeout(150);
      const last = await page.locator('[data-testid="last-handler"]').textContent();
      return {
        ok:
          /согласие/i.test(t || "") &&
          /согласие/i.test(primary || "") &&
          resolve?.includes('"kind":"consent"') &&
          last?.includes("handler: consent") &&
          !/Перейти к загрузке/i.test(primary || ""),
        primary,
        resolve,
        last,
      };
    },
  },
  {
    id: "upload",
    tz: 2,
    title: "Часть документов — получен ≠ проверен",
    assert: async (page) => {
      const t = await page.textContent("body");
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      const primary = (
        await page.getByRole("button", { name: /Перейти к загрузке документов/i }).textContent()
      )?.trim();
      return {
        ok:
          /Нужно загрузить/i.test(t || "") &&
          /Принят для текущего этапа/i.test(t || "") &&
          /1 из 2/i.test(t || "") &&
          /Выписка ИЛС/i.test(t || "") &&
          !!primary &&
          resolve?.includes('"kind":"upload"') &&
          resolve?.includes('"slotKey":"ils"'),
        primary,
        resolve,
        notes: "В комплекте: missing ИЛС + accepted трудовая",
      };
    },
  },
  {
    id: "waiting",
    tz: 3,
    title: "Всё передано — нет ложного требования",
    assert: async (page) => {
      const t = await page.textContent("body");
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      const hasUploadPrimary = await page.getByRole("button", { name: /Перейти к загрузке/i }).count();
      return {
        ok:
          /ничего не требуется|работает специалист/i.test(t || "") &&
          hasUploadPrimary === 0 &&
          resolve?.includes('"kind":"none"'),
        resolve,
        hasUploadPrimary,
      };
    },
  },
  {
    id: "reupload",
    tz: 4,
    title: "Нужна замена — причина и действие",
    assert: async (page) => {
      const t = await page.textContent("body");
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      return {
        ok:
          /повторно|замен|читаем|чётк/i.test(t || "") &&
          /Перейти к загрузке|Загрузить/i.test(t || "") &&
          resolve?.includes('"kind":"upload"'),
        resolve,
      };
    },
  },
  {
    id: "unavailable",
    tz: 5,
    title: "Ошибка / недоступность — без ложного прогресса",
    assert: async (page) => {
      const t = await page.textContent("body");
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      await page.getByRole("button", { name: "Вызвать handler сценария" }).click();
      await page.waitForTimeout(150);
      const last = await page.locator('[data-testid="last-handler"]').textContent();
      const hasUploadPrimary = await page.getByRole("button", { name: /Перейти к загрузке/i }).count();
      return {
        ok:
          resolve?.includes('"kind":"unavailable"') &&
          hasUploadPrimary === 0 &&
          /чат|обновите|недоступ/i.test(t || "") &&
          /skip|unavailable/i.test(last || ""),
        resolve,
        last,
        hasUploadPrimary,
      };
    },
  },
  {
    id: "contract",
    tz: "extra",
    title: "Договор — свой CTA + сумма",
    assert: async (page) => {
      const t = await page.textContent("body");
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      await page.getByRole("button", { name: "Вызвать handler сценария" }).click();
      const last = await page.locator('[data-testid="last-handler"]').textContent();
      return {
        ok:
          resolve?.includes('"kind":"contract"') &&
          /3[\s\u00a0]?000|3000/i.test(t || "") &&
          last?.includes("handler: contract") &&
          !/Где получить документ/i.test(t || ""),
        resolve,
        last,
      };
    },
  },
  {
    id: "pay",
    tz: "extra",
    title: "Оплата — свой CTA",
    assert: async (page) => {
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      await page.getByRole("button", { name: "Вызвать handler сценария" }).click();
      const last = await page.locator('[data-testid="last-handler"]').textContent();
      const t = await page.textContent("body");
      return {
        ok:
          resolve?.includes('"kind":"pay"') &&
          last?.includes("handler: pay") &&
          !/Где получить документ/i.test(t || ""),
        resolve,
        last,
      };
    },
  },
  {
    id: "result",
    tz: "extra",
    title: "Результат — свой CTA",
    assert: async (page) => {
      const resolve = await page.locator("#route-preview-handler-log code").textContent();
      await page.getByRole("button", { name: "Вызвать handler сценария" }).click();
      const last = await page.locator('[data-testid="last-handler"]').textContent();
      return {
        ok: resolve?.includes('"kind":"result"') && last?.includes("handler: result"),
        resolve,
        last,
      };
    },
  },
];

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  const results = [];

  for (const row of SCENARIOS) {
    await page.goto(`${base}/dev/route-preview?s=${row.id}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".case-route, .cabinet-case-layout");
    await page.waitForSelector("#route-preview-handler-log code");
    await page.waitForTimeout(350);
    const check = await row.assert(page);
    const shot = `scenario-${row.id}.png`;
    await page.screenshot({ path: path.join(outDir, shot), fullPage: false });
    const entry = {
      id: row.id,
      tz: row.tz,
      title: row.title,
      ok: !!check.ok,
      shot,
      ...check,
    };
    results.push(entry);
    console.log(`${check.ok ? "PASS" : "FAIL"} ${row.id}: ${row.title}`);
    if (!check.ok) {
      console.error(JSON.stringify(check, null, 2));
    }
  }

  await writeFile(
    path.join(outDir, "acceptance-scenarios.json"),
    JSON.stringify(
      {
        sha_note: "React preview only — не замена живого пользователя",
        base,
        at: new Date().toISOString(),
        results,
        allOk: results.every((r) => r.ok),
      },
      null,
      2,
    ),
    "utf8",
  );

  await browser.close();
  if (!results.every((r) => r.ok)) process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
