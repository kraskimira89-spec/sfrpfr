import assert from "node:assert/strict";
import test from "node:test";

import { noticeAfterQuickOrderSend } from "./quick-order-send.ts";

test("notice: отправка в MAX", () => {
  assert.match(noticeAfterQuickOrderSend(true), /отправлен клиенту в MAX/);
});

test("notice: MAX не ушёл", () => {
  assert.match(noticeAfterQuickOrderSend(false), /MAX не отправлен/);
});
