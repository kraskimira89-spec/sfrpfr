import assert from "node:assert/strict";
import test from "node:test";

import { clampChatWidth } from "./cabinet-case-layout.tsx";

test("clampChatWidth: нижняя граница 300", () => {
  assert.equal(clampChatWidth(100, 1440), 300);
});

test("clampChatWidth: верхняя граница 720 и 48% viewport", () => {
  assert.equal(clampChatWidth(900, 1440), 691); // floor(1440*0.48)=691
  assert.equal(clampChatWidth(900, 2000), 720);
});

test("clampChatWidth: значение внутри диапазона", () => {
  assert.equal(clampChatWidth(420, 1440), 420);
});
