import { test, expect } from "@playwright/test";

/**
 * Browser E2E предпроверки. Без PRECHECK_E2E_STAFF_TOKEN / API — skip (BLOCKED Auth).
 * Не подменяет API готовым result.
 */

const apiUrl = process.env.PRECHECK_E2E_API_URL || "";
const staffToken = process.env.PRECHECK_E2E_STAFF_TOKEN || "";
const caseId = process.env.PRECHECK_E2E_CASE_ID || "";
const acceptance = (process.env.PRECHECK_E2E_ACCEPTANCE || "").trim() === "1";

test.describe("precheck staff document check", () => {
  test.beforeEach(() => {
    const missing = !apiUrl || !staffToken || !caseId;
    if (!missing) return;
    const reason =
      "BLOCKED: нужны PRECHECK_E2E_API_URL, PRECHECK_E2E_STAFF_TOKEN, PRECHECK_E2E_CASE_ID (изолированный GoTrue / staff JWT).";
    if (acceptance) {
      throw new Error(reason);
    }
    test.skip(true, reason);
  });

  test("сценарий B: кнопка → job → результат без подмены API", async ({
    page,
  }) => {
    // Штатный вход admin уже выполнен cookie/JWT в storageState при наличии.
    await page.goto(`/cases/${caseId}`);
    await expect(page.getByRole("button", { name: /Проверить документы/i })).toBeVisible();

    const [req] = await Promise.all([
      page.waitForRequest(
        (r) =>
          r.url().includes(`/admin/cases/${caseId}/request-review`) &&
          r.method() === "POST",
      ),
      page.getByRole("button", { name: /Проверить документы/i }).click(),
    ]);
    expect(req).toBeTruthy();

    // Ждём terminal-состояние через UI/сеть, не sleep.
    await expect
      .poll(
        async () => {
          const res = await page.request.get(
            `${apiUrl.replace(/\/$/, "")}/api/portal/admin/cases/${caseId}`,
            { headers: { Authorization: `Bearer ${staffToken}` } },
          );
          if (!res.ok()) return "http_error";
          const body = await res.json();
          return String(body?.document_check?.status || "");
        },
        { timeout: 90_000 },
      )
      .toMatch(/completed|needs_action|failed/);
  });
});
