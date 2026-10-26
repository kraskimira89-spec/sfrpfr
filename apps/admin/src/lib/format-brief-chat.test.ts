import assert from "node:assert/strict";
import test from "node:test";
import {
  formatAskClientNextStepsTemplate,
  formatBriefChatTemplate,
  looksLikeBriefSummaryChat,
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
  assert.match(text, /краткая сверка/i);
  assert.match(text, /подробный письменный разбор/);
  assert.match(text, /подготовка обращений/i);
  // Сумма — один раз, без псевдокнопок «Получить разбор — 3 000 ₽».
  assert.equal((text.match(/3[\s\u00a0]?000/g) || []).length, 1);
  assert.match(text, /Вопросы можно задать здесь же/);
  assert.doesNotMatch(text, /какая у вас проблема|по-вашему/i);
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
  assert.match(text, /данных недостаточно/i);
  assert.match(text, /Тема — по северному/);
  assert.doesNotMatch(text, /вопрос по теме: возможные вопросы/i);
  assert.match(text, /Пришлите выписку ИЛС/);
  assert.doesNotMatch(text, /по-вашему|по вашему мнению/i);
  assert.doesNotMatch(text, /Подробная диагностика/);
  assert.doesNotMatch(text, /3000|3[\s\u00a0]?000/);
  // Без повторов: СФР — одна строка, «Следующий шаг» не дублируется.
  assert.equal((text.match(/СФР/g) || []).length, 1);
  assert.doesNotMatch(text, /Следующий шаг/);
});

test("без next_step: просим документы, не мнение о периодах", () => {
  const text = formatBriefChatTemplate(
    {
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
  assert.match(text, /пришлите.*выписку ИЛС/i);
  assert.match(text, /трудов/i);
  assert.doesNotMatch(text, /по-вашему|по вашему мнению|какие периоды.*учтены неверно/i);
  // ИЛС в сравнении и в просьбе документов — без опроса «какие периоды».
  assert.ok((text.match(/ИЛС/g) || []).length >= 1);
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

test("ask client — просьба документов, не резюме и не продажа", () => {
  const text = formatAskClientNextStepsTemplate(
    {
      items: [
        { text: "северный стаж", evidence: "client", basis: "со слов клиента" },
      ],
    },
    { diagAllowed: true, diagPaid: false },
  );
  assert.match(text, /пришлите.*выписку ИЛС/i);
  assert.match(text, /трудов/i);
  assert.doesNotMatch(text, /диагностик|3[\s\u00a0]?000|по-вашему|какие проблемы/i);
  assert.doesNotMatch(text, /Проверили ваши документы/);
});

test("сверка без расхождений: итог без вопросов клиенту", () => {
  const text = formatBriefChatTemplate({
    compare: { ran: true, discrepancies: 0, summary: "расхождений не найдено." },
    items: [{ text: "возможные вопросы по северному стажу", evidence: "needs_check" }],
  });
  assert.match(text, /Сверили выписку ИЛС с трудовой книжкой/);
  assert.doesNotMatch(text, /по-вашему|по вашему мнению|какие периоды.*учтены неверно/i);
  assert.doesNotMatch(text, /Пока данных недостаточно/);
});

test("looksLikeBriefSummaryChat: шаблон резюме — да, просьба документов — нет", () => {
  const brief = formatBriefChatTemplate(
    {
      has_justified_discrepancy: true,
      offer_diag_allowed: true,
      items: [{ text: "Период не отражён", evidence: "docs", basis: "ИЛС" }],
    },
    { diagAllowed: true },
  );
  assert.equal(looksLikeBriefSummaryChat(brief), true);
  assert.equal(looksLikeBriefSummaryChat(formatAskClientNextStepsTemplate()), false);
  assert.equal(looksLikeBriefSummaryChat("Здравствуйте! Пришлите документы."), false);
});
