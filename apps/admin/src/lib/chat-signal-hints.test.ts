import assert from "node:assert/strict";
import test from "node:test";
import { detectChatSignalHints } from "./chat-signal-hints.ts";

test("оплата в чате — подсказка, не paid", () => {
  const hints = detectChatSignalHints([
    { author_kind: "client", text: "Я уже оплатил счёт" },
  ]);
  assert.equal(hints.length, 1);
  assert.equal(hints[0].kind, "payment_claim");
  assert.match(hints[0].label, /проверить/i);
});

test("staff / bot не создают сигнал", () => {
  const hints = detectChatSignalHints([
    { author_kind: "staff", text: "Клиент оплатил" },
  ]);
  assert.equal(hints.length, 0);
});

test("подача через Госуслуги — заявление, не confirmation", () => {
  const hints = detectChatSignalHints([
    { author_kind: "client", text: "Подал через Госуслуги вчера" },
  ]);
  assert.equal(hints[0].kind, "submission_claim");
});
