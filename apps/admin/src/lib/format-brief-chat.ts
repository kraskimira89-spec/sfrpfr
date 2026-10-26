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
  /** Автосверка трудовой с ИЛС (сервер): ran — проводилась, discrepancies — сколько найдено. */
  compare?: { ran?: boolean; discrepancies?: number; summary?: string } | null;
};

export type FormatBriefChatOpts = {
  /** DIAG уже оплачен — не предлагать снова */
  diagPaid?: boolean;
  /** Серверный офер разрешён (обычно diag_offer.allowed) */
  diagAllowed?: boolean;
  /** Сумма офера; по умолчанию 3000 */
  diagAmountRub?: number;
};

/** Одна короткая строка о подаче; сервер убирает её, если её уже писали в переписке. */
const POSITION_LINE = "Обращение подаёте вы сами, решение принимает СФР.";

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
  "периоды в выписке ИЛС с записями трудовой книжки (или архивными справками)";

const DEFAULT_ASK_NEXT =
  "пришлите, пожалуйста, выписку ИЛС с Госуслуг (PDF) и сканы трудовой книжки или архивные справки о стаже — разбор делаем по документам";

function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

function withPeriod(s: string): string {
  return /[.!?]$/.test(s) ? s : `${s}.`;
}

/** «возможные вопросы по северному стажу» → «по северному стажу» (без «вопрос по теме: вопросы»). */
function themeText(raw: string): string {
  return raw.replace(/^возможн\S*\s+(?:вопросы\s+)?/i, "").trim() || "по вашей теме";
}

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
    "Это краткая сверка по документам (трудовая, выписка ИЛС, справки). Пока нельзя считать эти периоды полностью учтёнными.",
  );
  lines.push("");

  if (opts.diagPaid) {
    lines.push(
      "Подробная диагностика уже оплачена: разберём отмеченные периоды по документам и пришлём письменный результат.",
    );
  } else if (opts.diagAllowed) {
    lines.push(
      `Следующий платный шаг — подробный письменный разбор за ${amount.toLocaleString("ru-RU")} ₽ ` +
        "или подготовка обращений в СФР (отдельная услуга).",
    );
    lines.push(
      "Если нужен подробный разбор — напишите «Да, нужен разбор», пришлём ссылку на оплату. Вопросы можно задать здесь же.",
    );
  } else {
    lines.push(
      "Пришлите недостающие документы по отмеченным пунктам прямо в этот чат — краткий анализ строим по бумагам, не по оценке «на глаз».",
    );
  }

  lines.push("");
  lines.push(POSITION_LINE);
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function formatInsufficient(
  soft: BriefChatItem[],
  brief: HonestBriefForChat,
): string {
  const theme = themeText(cleanLine(soft[0]?.text));
  const basis = cleanLine(soft[0]?.basis);
  const compareHint =
    isUsable(basis) && !SOURCE_LABEL_RE.test(basis) ? basis : DEFAULT_COMPARE;
  const next = sanitizeNextStep(brief.next_step) || DEFAULT_ASK_NEXT;

  const lines = [
    "Пока данных недостаточно, чтобы сказать, есть ли расхождение.",
    "",
    `Тема — ${theme}. Проверку делаем по документам: сверим ${compareHint}.`,
    "",
    withPeriod(capitalize(next)),
    "",
    POSITION_LINE,
  ];
  return lines.join("\n").trim();
}

function formatComparedClean(): string {
  return [
    "Сверили выписку ИЛС с трудовой книжкой: все периоды работы в выписке есть, северные отметки совпадают — расхождений не нашли.",
    "",
    "Если по какому-то периоду у вас есть другие документы (например, архивные справки), пришлите их — проверим и их.",
    "",
    POSITION_LINE,
  ].join("\n");
}

function formatEmptyOrLimit(brief: HonestBriefForChat): string {
  const headline =
    cleanLine(brief.headline) ||
    "По представленным документам автоматическая проверка не выявила очевидных расхождений";
  const next = sanitizeNextStep(brief.next_step);
  const lines = [
    withPeriod(headline),
    "Это предварительная проверка комплекта, а не полный разбор.",
  ];
  if (next) {
    lines.push("");
    lines.push(withPeriod(capitalize(next)));
  }
  lines.push("");
  lines.push(POSITION_LINE);
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

  if (brief.compare?.ran) {
    return formatComparedClean();
  }

  if (soft.length > 0) {
    return formatInsufficient(soft, brief);
  }

  return formatEmptyOrLimit(brief);
}

/**
 * Короткая просьба документов в чат — отдельно от резюме сверки.
 * Не дублирует formatBriefChatTemplate (кнопка «Подставить резюме»).
 */
export function formatAskClientNextStepsTemplate(
  _brief?: HonestBriefForChat | null,
  _opts: FormatBriefChatOpts = {},
): string {
  return [
    "Чтобы сверить стаж, пришлите, пожалуйста, выписку ИЛС с Госуслуг (PDF) и сканы трудовой книжки или справки о стаже прямо в этот чат.",
    "Краткий разбор сделаем по документам — заранее формулировать «проблему» не нужно.",
    "",
    POSITION_LINE,
  ].join("\n");
}
