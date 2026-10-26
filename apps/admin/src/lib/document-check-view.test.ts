import assert from "node:assert/strict";
import test from "node:test";
import { buildCheckView } from "./document-check-view.ts";

const REAL_CASE = {
  documents_checked: 12,
  unique_documents: 4,
  text_extracted: 11,
  needs_recognition: 1,
  needs_manual_review: 0,
  types_found: ["ils", "other", "workbook"],
  missing_for_task: [],
  unreadable_files: ["22-10-26_12-27(1).png"],
  honest_brief: {
    items: [
      {
        text: "возможные вопросы по северному / льготному стажу",
        evidence: "needs_check",
        basis: "анкета / формулировка клиента",
      },
      { text: "возможные расхождения дат или периодов стажа", evidence: "client" },
    ],
  },
};

test("реальное дело: 4 уникальных файла, нечитаемый PNG, шаг — запросить документы", () => {
  const v = buildCheckView(REAL_CASE, { offerAllowed: false, diagPaid: true });
  assert.equal(v.kit.unique, 4);
  assert.equal(v.kit.duplicates, 8);
  assert.deepEqual(v.kit.types, ["выписка ИЛС", "трудовая книжка", "прочее"]);
  assert.equal(v.kit.hasCore, true);
  assert.deepEqual(v.read.unreadable, ["22-10-26_12-27(1).png"]);
  assert.deepEqual(v.read.unreadableDocs, []);
  // Счёт по уникальным файлам, как в блоке 1 (не 11 из 12 с повторами).
  assert.equal(v.read.total, 4);
  assert.equal(v.read.textOk, 3);
  assert.equal(v.findings.docs.length, 0);
  assert.equal(v.findings.questionnaire.length, 1);
  assert.equal(v.findings.client.length, 1);
  assert.equal(v.next.kind, "clarify");
  assert.match(v.next.text, /ИЛС|трудов/i);
  assert.doesNotMatch(v.next.text, /по его мнению|по-вашему|какие проблемы/i);
});

test("расхождения в документах без офера: итог сверки, не мнение клиента", () => {
  const v = buildCheckView(
    {
      ...REAL_CASE,
      honest_brief: { items: [{ text: "период не отражён", evidence: "docs", basis: "ИЛС" }] },
    },
    { offerAllowed: false, diagPaid: false },
  );
  assert.equal(v.next.kind, "discuss");
  assert.match(v.next.text, /резюме|сверк|справк|трудов/i);
  assert.doesNotMatch(v.next.text, /как ему удобнее|по его мнению|напишите.*период/i);
});

test("не хватает ИЛС — первым делом запросить документ", () => {
  const v = buildCheckView(
    { ...REAL_CASE, types_found: ["workbook"], missing_for_task: ["Выписка ИЛС"] },
    { offerAllowed: false, diagPaid: false },
  );
  assert.equal(v.kit.hasCore, false);
  assert.equal(v.next.kind, "ask_docs");
  assert.match(v.next.text, /Выписка ИЛС/);
});

test("расхождение из документов + офер → предложить диагностику", () => {
  const v = buildCheckView(
    {
      ...REAL_CASE,
      honest_brief: { items: [{ text: "период не отражён", evidence: "docs", basis: "ИЛС" }] },
    },
    { offerAllowed: true, diagPaid: false },
  );
  assert.equal(v.findings.docs.length, 1);
  assert.equal(v.next.kind, "offer");
  assert.match(v.next.text, /краткая сверка|подробный разбор|обращен/i);
  assert.doesNotMatch(v.next.text, /какая у вас проблема/i);
});

test("расхождение из документов, DIAG оплачен → готовить разбор, без продажи", () => {
  const v = buildCheckView(
    {
      ...REAL_CASE,
      honest_brief: { items: [{ text: "период не отражён", evidence: "docs" }] },
    },
    { offerAllowed: true, diagPaid: true },
  );
  assert.equal(v.next.kind, "paid");
  assert.doesNotMatch(v.next.text, /3[\s\u00a0]?000/);
});

test("всё прочитано, тем нет → переходить к сверке", () => {
  const v = buildCheckView(
    {
      documents_checked: 2,
      text_extracted: 2,
      types_found: ["ils", "workbook"],
      honest_brief: { items: [] },
    },
    { offerAllowed: false, diagPaid: false },
  );
  assert.equal(v.next.kind, "proceed");
});

test("сверка без расхождений: не спрашиваем клиента, а сообщаем итог", () => {
  const v = buildCheckView(
    { ...REAL_CASE, stazh_compare: { ran: true, summary: "Сверили: расхождений не найдено." } },
    { offerAllowed: false, diagPaid: true },
  );
  assert.equal(v.compare.ran, true);
  assert.equal(v.next.kind, "proceed");
  assert.match(v.next.title, /расхождений нет/i);
});

test("сверка нашла расхождение: шаг — готовить разбор, а не уточнять", () => {
  const v = buildCheckView(
    {
      ...REAL_CASE,
      stazh_compare: { ran: true, summary: "найдено расхождений: 1." },
      honest_brief: {
        items: [
          { text: "Северный стаж учтён не за весь период", evidence: "docs", basis: "…" },
          ...REAL_CASE.honest_brief.items,
        ],
      },
    },
    { offerAllowed: false, diagPaid: true },
  );
  assert.equal(v.next.kind, "paid");
  assert.equal(v.findings.docs.length, 1);
});
