/**
 * Текст резюме для подстановки в чат сотрудника.
 * Не обещает перерасчёт / прибавку / гарантию учёта стажа.
 */

export type BriefChatItem = {
  text?: string;
  evidence?: string;
  evidence_label?: string;
  basis?: string;
};

export type HonestBriefForChat = {
  headline?: string;
  next_step?: string;
  has_justified_discrepancy?: boolean;
  offer_diag_allowed?: boolean;
  offer_amount_rub?: number;
  items?: BriefChatItem[];
  disclaimer?: string;
};

export type FormatBriefChatOpts = {
  /** DIAG уже оплачен — не предлагать снова */
  diagPaid?: boolean;
  /** Серверный офер разрешён (обычно diag_offer.allowed) */
  diagAllowed?: boolean;
  /** Сумма офера; по умолчанию 3000 */
  diagAmountRub?: number;
};

const SFR_LINE =
  "Решение об учёте стажа и назначении пенсии принимает СФР.";
const PREPARE_LINE =
  "Мы готовим документы, проект обращения и план — расскажем по шагам, но подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

function cleanLine(s: string | undefined | null): string {
  return String(s || "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Не отдавать клиенту незаполненные [скобки] и пустые плейсхолдеры. */
function isUsable(s: string): boolean {
  if (!s) return false;
  if (/\[[^\]]+\]/.test(s)) return false;
  return true;
}

/** next_step бэкенда написан для MAX-бота («ответьте кнопкой», /help) — в чат сотрудника не годится. */
const BOT_ONLY_RE = /\/help|кнопк/i;

/** basis у пунктов анкеты — источник («анкета», «со слов клиента»), а не что сверять. */
const SOURCE_LABEL_RE = /анкет|со слов|формулировк/i;

const DEFAULT_COMPARE =
  "периоды в выписке ИЛС и в трудовой книжке (или архивных справках)";

const DEFAULT_ASK_NEXT =
  "напишите, какие именно периоды (годы и место работы), по-вашему, учтены неверно — специалист сверит их с выпиской ИЛС и трудовой книжкой";

export function sanitizeNextStep(raw: string | undefined | null): string {
  const s = cleanLine(raw).replace(/^(следующий шаг:\s*)+/i, "").trim();
  if (!s || BOT_ONLY_RE.test(s)) return "";
  return s;
}

function docsItems(items: BriefChatItem[]): BriefChatItem[] {
  return items.filter((i) => (i.evidence || "").toLowerCase() === "docs" && isUsable(cleanLine(i.text)));
}

function softItems(items: BriefChatItem[]): BriefChatItem[] {
  return items.filter((i) => {
    const ev = (i.evidence || "").toLowerCase();
    return (ev === "client" || ev === "needs_check") && isUsable(cleanLine(i.text));
  });
}

function formatDocPoint(item: BriefChatItem, n: number): string {
  const title = cleanLine(item.text);
  const basis = cleanLine(item.basis);
  const lines = [`${n}. ${title}`];
  if (isUsable(basis)) lines.push(basis);
  return lines.join("\n");
}

function formatDocsConfirmed(
  docs: BriefChatItem[],
  opts: FormatBriefChatOpts,
): string {
  const amount = opts.diagAmountRub ?? 3000;
  const lines: string[] = [
    "Проверили ваши документы. Вот что требует внимания.",
    "",
  ];
  docs.slice(0, 2).forEach((item, idx) => {
    lines.push(formatDocPoint(item, idx + 1));
    lines.push("");
  });
  lines.push("Что это означает для вас");
  lines.push(
    "Пока нельзя подтвердить, что эти периоды учтены корректно. Нужно выяснить причину расхождений и определить, какими документами их можно подтвердить.",
  );
  lines.push("");

  if (opts.diagPaid) {
    lines.push(
      "Подробная диагностика уже оплачена. Далее: разбор отмеченных периодов и письменный результат по документам — без обещания суммы выплат.",
    );
    lines.push("Если остались вопросы — напишите специалисту в этот чат.");
  } else if (opts.diagAllowed) {
    lines.push(`Подробная диагностика — ${amount.toLocaleString("ru-RU")} ₽`);
    lines.push(
      "Разберём отмеченные периоды и подготовим письменный результат: что подтверждается документами, какие вопросы остаются и что нужно запросить или уточнить.",
    );
    lines.push("");
    lines.push(`Получить подробный разбор — ${amount.toLocaleString("ru-RU")} ₽`);
    lines.push("Задать вопрос специалисту");
  } else {
    lines.push(
      "Сейчас предлагаем уточнить документы по отмеченным пунктам. Счёт на диагностику откроем, когда основание подтверждено сервером.",
    );
  }

  lines.push("");
  lines.push(SFR_LINE);
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function formatInsufficient(
  soft: BriefChatItem[],
  brief: HonestBriefForChat,
): string {
  const theme = cleanLine(soft[0]?.text) || "вашей теме обращения";
  const basis = cleanLine(soft[0]?.basis);
  const compareHint =
    isUsable(basis) && !SOURCE_LABEL_RE.test(basis) ? basis : DEFAULT_COMPARE;
  const next = sanitizeNextStep(brief.next_step) || DEFAULT_ASK_NEXT;

  const lines = [
    "Для проверки пока недостаточно данных.",
    "",
    `Вы указали вопрос по теме: ${theme}. Чтобы установить, есть ли расхождение, необходимо сопоставить: ${compareHint}.`,
    "",
    `Следующий шаг: ${next}`,
    "",
    "Сейчас мы не можем обоснованно утверждать, что стаж учтён неправильно.",
    "",
    PREPARE_LINE,
  ];
  return lines.join("\n").trim();
}

function formatEmptyOrLimit(brief: HonestBriefForChat): string {
  const headline =
    cleanLine(brief.headline) ||
    "По представленным документам автоматическая проверка не выявила очевидных расхождений.";
  const next = sanitizeNextStep(brief.next_step);
  const lines = [
    "Результат предварительной проверки",
    "",
    headline,
    "",
    "Мы не создаём видимость полной диагностики: без подтверждённых расхождений в документах нельзя обещать «исправление стажа».",
  ];
  if (next) {
    lines.push("");
    lines.push(`Следующий шаг: ${next}`);
  }
  lines.push("");
  lines.push(PREPARE_LINE);
  return lines.join("\n").trim();
}

/**
 * Собирает текст для «Подставить резюме в чат».
 */
export function formatBriefChatTemplate(
  brief: HonestBriefForChat,
  opts: FormatBriefChatOpts = {},
): string {
  const items = Array.isArray(brief.items) ? brief.items : [];
  const docs = docsItems(items);
  const soft = softItems(items);

  const diagAllowed =
    opts.diagAllowed ??
    Boolean(brief.offer_diag_allowed && brief.has_justified_discrepancy);

  if (docs.length > 0) {
    return formatDocsConfirmed(docs, {
      ...opts,
      diagAllowed: Boolean(diagAllowed) && !opts.diagPaid,
      diagAmountRub: opts.diagAmountRub ?? brief.offer_amount_rub ?? 3000,
    });
  }

  if (soft.length > 0) {
    return formatInsufficient(soft, brief);
  }

  return formatEmptyOrLimit(brief);
}

/**
 * Нейтральный запрос следующих шагов — без продажи на неподтверждённом.
 */
export function formatAskClientNextStepsTemplate(
  brief?: HonestBriefForChat | null,
  opts: FormatBriefChatOpts = {},
): string {
  if (brief) {
    const items = Array.isArray(brief.items) ? brief.items : [];
    const docs = docsItems(items);
    if (docs.length > 0 && opts.diagAllowed && !opts.diagPaid) {
      return formatBriefChatTemplate(brief, opts);
    }
    if (docs.length === 0 && softItems(items).length > 0) {
      return formatInsufficient(softItems(items), brief);
    }
  }
  return [
    "Здравствуйте! Кратко сверили комплект.",
    "Напишите, пожалуйста, удобный следующий шаг: уточнить документы или задать вопрос специалисту.",
    "Пока нет подтверждённого расхождения в документах, мы не предлагаем оплату диагностики.",
    PREPARE_LINE,
  ].join("\n");
}
