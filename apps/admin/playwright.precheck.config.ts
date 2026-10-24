import { defineConfig } from "@playwright/test";

/**
 * Предлагаемый harness precheck browser E2E (цикл 5).
 * Запуск только при установленных PRECHECK_E2E_* и staff JWT.
 * Без GoTrue/Auth на стенде сценарии skip — критерий не снижаем.
 */
const baseURL = process.env.PRECHECK_E2E_BASE_URL || "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  reporter: [["list"]],
});
