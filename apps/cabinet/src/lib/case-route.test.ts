import assert from "node:assert/strict";
import test from "node:test";

import {
  addedDocumentsFromWork,
  chaptersFromWork,
  currentChapterId,
  kitMarksFromWork,
  nextStepFromWork,
  requiredProgressLabel,
  resolveRoutePrimaryAction,
  type ClientWorkLike,
} from "./case-route.ts";

function baseWork(over: Partial<ClientWorkLike> = {}): ClientWorkLike {
  return {
    status_key: "waiting_docs",
    status_label: "Ждём документы",
    status_hint: "Нужна выписка",
    now_need: "Загрузить Выписка ИЛС",
    cta_key: "upload",
    cta_label: "Перейти к загрузке документов",
    consent_ok: true,
    required_uploaded: 0,
    required_total: 2,
    stages: [
      { n: 1, title: "1", hint: "", state: "done" },
      { n: 2, title: "2", hint: "", state: "current" },
      { n: 3, title: "3", hint: "", state: "todo" },
      { n: 4, title: "4", hint: "", state: "todo" },
      { n: 5, title: "5", hint: "", state: "todo" },
    ],
    documents: [
      {
        key: "ils",
        title: "Выписка ИЛС",
        need: "required",
        status: "missing",
        status_label: "Нужно загрузить",
      },
      {
        key: "labor",
        title: "Трудовая",
        need: "required",
        status: "missing",
        status_label: "Нужно загрузить",
      },
    ],
    next_actions: ["Загрузить: Выписка ИЛС"],
    ils_howto_url: "https://example.test/ils",
    order: { amount_rub: 3000, order_id: null },
    result: { ready: false, document_id: null },
    ...over,
  };
}

test("главы: текущая — Документы", () => {
  const chapters = chaptersFromWork(baseWork());
  assert.equal(chapters[1]?.label, "Документы");
  assert.equal(chapters[1]?.state, "current");
  assert.equal(currentChapterId(baseWork()), "documents");
});

test("upload: howto и «не могу получить» только для документов", () => {
  const step = nextStepFromWork(baseWork());
  assert.equal(step.mode, "action");
  assert.equal(step.showCantGetDocument, true);
  assert.equal(step.howtoUrl, "https://example.test/ils");
  assert.ok(step.showContinueLaterHint);
});

test("unknown CTA: нейтральная недоступность без документных подсказок", () => {
  const work = baseWork({
    cta_key: "mystery_future_cta",
    cta_label: "Странная кнопка",
    now_need: "Неизвестное действие",
  });
  const step = nextStepFromWork(work);
  assert.equal(step.showCantGetDocument, false);
  assert.equal(step.showContinueLaterHint, false);
  assert.equal(step.howtoUrl, null);
  assert.equal(step.primaryLabel, null);
  assert.equal(resolveRoutePrimaryAction(work).kind, "unavailable");
});

test("consent: без документных подсказок и без fallback upload", () => {
  const work = baseWork({
    status_key: "consent",
    cta_key: "consent",
    consent_ok: false,
    now_need: "Подтвердить согласие",
    cta_label: "Даю согласие",
  });
  const step = nextStepFromWork(work);
  assert.equal(step.showCantGetDocument, false);
  assert.equal(step.howtoUrl, null);
  assert.equal(resolveRoutePrimaryAction(work).kind, "consent");
});

test("pay без order_id: unavailable, не upload", () => {
  const work = baseWork({
    cta_key: "pay",
    now_need: "Оплатить диагностику",
    cta_label: "Оплатить",
    order: { amount_rub: 3000, order_id: null },
  });
  const step = nextStepFromWork(work);
  assert.equal(step.showCantGetDocument, false);
  assert.match(String(step.consequenceHint), /3\s?000/);
  assert.equal(resolveRoutePrimaryAction(work).kind, "unavailable");
});

test("pay с order_id: только pay", () => {
  const action = resolveRoutePrimaryAction(
    baseWork({
      cta_key: "pay",
      order: { amount_rub: 3000, order_id: "ord-1" },
    }),
  );
  assert.deepEqual(action, { kind: "pay", orderId: "ord-1" });
});

test("contract: пояснение суммы; без handler — unavailable", () => {
  const work = baseWork({
    cta_key: "contract",
    now_need: "Принять условия",
    cta_label: "Принять условия",
    order: { amount_rub: 3000, order_id: null },
  });
  const step = nextStepFromWork(work);
  assert.match(String(step.consequenceHint), /счёт на диагностику/);
  assert.match(String(step.consequenceHint), /3\s?000/);
  assert.equal(step.showCantGetDocument, false);
  assert.equal(resolveRoutePrimaryAction(work, { hasContractHandler: false }).kind, "unavailable");
  assert.equal(resolveRoutePrimaryAction(work, { hasContractHandler: true }).kind, "contract");
});

test("result без document_id: unavailable, не upload", () => {
  const work = baseWork({
    cta_key: "result",
    now_need: "Открыть результат",
    result: { ready: true, document_id: null },
  });
  assert.equal(nextStepFromWork(work).showCantGetDocument, false);
  assert.equal(resolveRoutePrimaryAction(work).kind, "unavailable");
});

test("upload без слота: unavailable", () => {
  const work = baseWork({
    documents: [
      {
        key: "ils",
        title: "Выписка ИЛС",
        need: "required",
        status: "awaiting",
        status_label: "получен",
        added_at: "25 октября, 12:00",
      },
      {
        key: "labor",
        title: "Трудовая",
        need: "required",
        status: "awaiting",
        status_label: "получен",
        added_at: "25 октября, 12:05",
      },
    ],
  });
  assert.equal(resolveRoutePrimaryAction(work).kind, "unavailable");
});

test("ожидание специалиста", () => {
  const step = nextStepFromWork(
    baseWork({
      status_key: "docs_review",
      cta_key: "wait",
      next_actions: [],
      now_need: "Сейчас от вас ничего не требуется",
      stages: [
        { n: 1, title: "1", hint: "", state: "done" },
        { n: 2, title: "2", hint: "", state: "done" },
        { n: 3, title: "3", hint: "", state: "current" },
        { n: 4, title: "4", hint: "", state: "todo" },
        { n: 5, title: "5", hint: "", state: "todo" },
      ],
    }),
  );
  assert.equal(step.mode, "waiting");
  assert.equal(step.primaryLabel, null);
  assert.equal(step.showCantGetDocument, false);
});

test("добавленные документы: только факт загрузки, не принятие", () => {
  const rows = addedDocumentsFromWork(
    baseWork({
      documents: [
        {
          key: "ils",
          title: "Выписка ИЛС",
          need: "required",
          status: "accepted",
          status_label: "Принят",
          added_at: "25 октября, 12:00",
        },
        {
          key: "labor",
          title: "Трудовая",
          need: "required",
          status: "reupload",
          status_label: "Нужно повторно",
          added_at: "25 октября, 13:00",
        },
      ],
    }),
  );
  assert.equal(rows.length, 2);
  assert.match(rows[0]!.text, /Вы добавили документ/);
  assert.match(rows[1]!.text, /Вы добавили документ/);
  assert.ok(!rows.some((r) => /Принят|замена/i.test(r.text)));
});

test("комплект: получен ≠ принят", () => {
  const marks = kitMarksFromWork(
    baseWork({
      documents: [
        {
          key: "ils",
          title: "Выписка ИЛС",
          need: "required",
          status: "awaiting",
          status_label: "Загружен — ожидает проверки",
          added_at: "25 октября, 12:00",
        },
        {
          key: "labor",
          title: "Трудовая",
          need: "required",
          status: "accepted",
          status_label: "Принят специалистом",
        },
      ],
      required_uploaded: 1,
      required_total: 2,
    }),
  );
  const ils = marks.find((m) => m.key === "ils");
  const labor = marks.find((m) => m.key === "labor");
  assert.equal(ils?.mark, "checking");
  assert.match(String(ils?.statusText), /получен/i);
  assert.equal(labor?.mark, "done");
  assert.equal(
    requiredProgressLabel(baseWork({ required_uploaded: 1, required_total: 2 })),
    "Обязательных документов: 1 из 2",
  );
});
