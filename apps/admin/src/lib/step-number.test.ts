import assert from "node:assert/strict";
import test from "node:test";
import { childPrefix, stepLabel } from "./step-number.ts";

test("внутри этапа 3: 3.1, 3.2", () => {
  assert.equal(stepLabel("3", 1), "3.1");
  assert.equal(stepLabel("3", 2), "3.2");
});

test("третий уровень: 3.1.1", () => {
  assert.equal(stepLabel(childPrefix("3", 1), 1), "3.1.1");
  assert.equal(stepLabel(childPrefix("3", 1), 4), "3.1.4");
});

test("без родителя — обычная нумерация «1.»", () => {
  assert.equal(stepLabel("", 1), "1.");
  assert.equal(childPrefix("", 2), "2");
});
