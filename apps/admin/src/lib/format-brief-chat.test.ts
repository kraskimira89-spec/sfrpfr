import assert from "node:assert/strict";
import test from "node:test";
import {
  formatAskClientNextStepsTemplate,
  formatBriefChatTemplate,
  sanitizeNextStep,
} from "./format-brief-chat.ts";

test("docs: включает basis и офер DIAG один раз", () => {
  const text = formatBriefChatTemplate(
    {
      has_justified_discrepancy: true,
      offer_diag_allowed: true,
      offer_amount_rub: 3000,
      items: [
        {
          text: "Период не отражён в ИЛС",
          evidence: "docs",
          basis: "В трудовой указан период 01.1998–06.2001. В выписке ИЛС этот период отсутствует.",
        },
        {
          text: "Расхождение дат увольнения",
          evidence: "docs",
          basis: "В справке дата 15.03.2010, в ИЛС — 01.04.2010.",
        },
      ],
    },
    { diagAllowed: true, diagPaid: false },
  );
  assert.match(text, /Проверили ваши документы/);
  assert.match(text, /В трудовой указан период/);
  assert.match(text, /Подробная диагностика/);
  assert.match(text, /3000|3[\s\u00a0]?000/);
  assert.match(text, /Задать вопрос специалисту/);
  assert.doesNotMatch(text, /\/help/i);
  assert.doesNotMatch(text, /ответьте кнопкой/i);
  assert.doesNotMatch(text, /перерасч[её]т|прибавк/i);
});

test("docs + DIAG paid: без повторного офера", () => {
  const text = formatBriefChatTemplate(
    {
      items: [
        {
          text: "Период не отражён",
          evidence: "docs",
          basis: "ИЛС не содержит период из трудовой.",
        },
      ],
    },
    { diagAllowed: true, diagPaid: true },
  );
  assert.match(text, /уже оплачена/i);
  assert.doesNotMatch(text, /Получить подробный разбор/);
});

test("client / needs_check: сначала данные, не продажа", () => {
  const text = formatBriefChatTemplate(
    {
      next_step: "пришлите выписку ИЛС и разворот трудовой",
      items: [
        {
          text: "возможные вопросы по северному / льготному стажу",
          evidence: "needs_check",
          basis: "анкета / формулировка клиента",
        },
      ],
    },
    { diagAllowed: false },
  );
  assert.match(text, /недостаточно данных/i);
  assert.match(text, /северн/i);
  assert.match(text, /Следующий шаг/);
  assert.doesNotMatch(text, /Подробная диагностика/);
  assert.doesNotMatch(text, /3000|3[\s\u00a0]?000/);
  assert.match(text, /не можем обоснованно утверждать/i);
});

test("пусто: ограничение проверки без офера", () => {
  const text = formatBriefChatTemplate(
    {
      headline: "По представленным документам автоматическая проверка не выявила очевидных расхождений",
      items: [],
    },
    { diagAllowed: false },
  );
  assert.match(text, /не выявила очевидных расхождений|ограничен/i);
  assert.doesNotMatch(text, /Подробная диагностика —/);
  assert.doesNotMatch(text, /\[/);
});

test("реальное дело: анкета + текст бота в next_step не утекают клиенту", () => {
  const text = formatBriefChatTemplate(
    {
      has_justified_discrepancy: true,
      offer_diag_allowed: true,
      next_step:
        "Следующий шаг: если нужен подробный разбор — ответьте кнопкой ниже (или напишите специалисту /help).",
      items: [
        {
          text: "возможные вопросы по северному / льготному стажу",
          evidence: "needs_check",
          basis: "анкета / формулировка клиента",
        },
        {
          text: "возможные расхождения дат или периодов стажа",
          evidence: "client",
          basis: "со слов клиента",
        },
      ],
    },
    { diagAllowed: true, diagPaid: false },
  );
  assert.doesNotMatch(text, /\/help/i);
  assert.doesNotMatch(text, /кнопк/i);
  assert.doesNotMatch(text, /Следующий шаг:\s*Следующий шаг/i);
  assert.doesNotMatch(text, /сопоставить:\s*анкета/i);
  assert.match(text, /выписк\S* ИЛС/i);
  assert.doesNotMatch(text, /3[\s\u00a0]?000/);
});

test("sanitizeNextStep: снимает префикс, отбрасывает текст бота", () => {
  assert.equal(sanitizeNextStep("Следующий шаг: пришлите выписку ИЛС"), "пришлите выписку ИЛС");
  assert.equal(
    sanitizeNextStep("Следующий шаг: уточните, что сверить, или напишите специалисту /help."),
    "",
  );
  assert.equal(sanitizeNextStep(""), "");
});

test("ask client без docs — без продажи", () => {
  const text = formatAskClientNextStepsTemplate(
    {
      items: [
        { text: "северный стаж", evidence: "client", basis: "со слов клиента" },
      ],
    },
    { diagAllowed: false },
  );
  assert.doesNotMatch(text, /диагностик[аи].*3000|3[\s\u00a0]?000/i);
  assert.match(text, /недостаточно данных|не предлагаем оплату/i);
});
