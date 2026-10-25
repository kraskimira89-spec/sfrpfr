import assert from "node:assert/strict";
import test from "node:test";
import {
  initialAccordion,
  nextStageId,
  openStageOf,
  stageStepNumber,
  toggleAccordion,
} from "./case-funnel-accordion.ts";

test("по умолчанию открыт текущий этап", () => {
  const s = initialAccordion("a");
  assert.equal(openStageOf(s, "a", "documents"), "documents");
});

test("открыт только один этап: клик по другому закрывает предыдущий", () => {
  let s = initialAccordion("a");
  s = toggleAccordion(s, "a", "closure", "documents");
  assert.equal(openStageOf(s, "a", "documents"), "closure");
  s = toggleAccordion(s, "a", "precheck_summary", "documents");
  assert.equal(openStageOf(s, "a", "documents"), "precheck_summary");
});

test("повторный клик закрывает этап; смена current не открывает его заново", () => {
  let s = initialAccordion("a");
  s = toggleAccordion(s, "a", "documents", "documents");
  assert.equal(openStageOf(s, "a", "documents"), null);
  assert.equal(openStageOf(s, "a", "precheck_summary"), null);
});

test("смена дела сбрасывает ручной выбор", () => {
  let s = initialAccordion("a");
  s = toggleAccordion(s, "a", "closure", "documents");
  assert.equal(openStageOf(s, "b", "documents"), "documents");
  s = toggleAccordion(s, "b", "documents", "documents");
  assert.equal(s.caseId, "b");
  assert.equal(openStageOf(s, "b", "documents"), null);
});

test("номер ступени и следующая ступень по STAGE_IDS", () => {
  assert.equal(stageStepNumber("contact_consents"), 1);
  assert.equal(stageStepNumber("closure"), 13);
  assert.equal(nextStageId("documents"), "precheck_summary");
  assert.equal(nextStageId("closure"), null);
});
