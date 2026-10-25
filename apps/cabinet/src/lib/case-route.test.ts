import assert from "node:assert/strict";
import test from "node:test";

import {
  chaptersFromWork,
  currentChapterId,
  kitMarksFromWork,
  nextStepFromWork,
  requiredProgressLabel,
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
    ...over,
  };
}

test("главы: текущая — Документы", () => {
  const chapters = chaptersFromWork(baseWork());
  assert.equal(chapters[1]?.label, "Документы");
  assert.equal(chapters[1]?.state, "current");
  assert.equal(currentChapterId(baseWork()), "documents");
});

test("следующий шаг: одно действие + howto для ИЛС", () => {
  const step = nextStepFromWork(baseWork());
  assert.equal(step.mode, "action");
  assert.match(step.title, /ИЛС|Загрузить/i);
  assert.equal(step.howtoUrl, "https://example.test/ils");
  assert.ok(step.primaryLabel);
});

test("ожидание специалиста без ложного upload", () => {
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
  assert.equal(
    currentChapterId(
      baseWork({
        status_key: "docs_review",
        cta_key: "wait",
        next_actions: [],
        stages: [
          { n: 1, title: "1", hint: "", state: "done" },
          { n: 2, title: "2", hint: "", state: "done" },
          { n: 3, title: "3", hint: "", state: "current" },
          { n: 4, title: "4", hint: "", state: "todo" },
          { n: 5, title: "5", hint: "", state: "todo" },
        ],
      }),
    ),
    "review",
  );
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
  assert.equal(requiredProgressLabel(baseWork({ required_uploaded: 1, required_total: 2 })), "Обязательных документов: 1 из 2");
});
