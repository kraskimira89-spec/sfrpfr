import assert from "node:assert/strict";
import test from "node:test";

import { labelAuditAction } from "../../../../shared/ui-labels.ts";

test("audit: staff_case_viewed по-русски", () => {
  assert.equal(labelAuditAction("staff_case_viewed"), "Сотрудник открыл дело");
});

test("audit: order_created с пакетом", () => {
  assert.match(labelAuditAction("order_created:ACCOMP"), /Создан счёт/);
  assert.match(labelAuditAction("order_created:ACCOMP"), /Подготовка/);
});

test("audit: неизвестный код остаётся как есть", () => {
  assert.equal(labelAuditAction("custom_weird_event"), "custom_weird_event");
});
