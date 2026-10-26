/**
 * Результат «Проверить документы» → блоки по ходу процесса для сотрудника:
 * что получили → что прочитали → что видно по сути → что делать дальше.
 */

export type CheckBriefItem = {
  text?: string;
  evidence?: string;
  evidence_label?: string;
  basis?: string;
};

export type CheckResultInput = {
  documents_checked?: number;
  unique_documents?: number;
  text_extracted?: number;
  needs_recognition?: number;
  needs_manual_review?: number;
  types_found?: string[];
  missing_for_task?: string[];
  unreadable_files?: string[];
  /** Нечитаемые файлы с id (для удаления из UI проверки). */
  unreadable_docs?: { filename?: string; document_ids?: string[] }[];
  manual_files?: string[];
  honest_brief?: { items?: CheckBriefItem[] } | null;
  stazh_compare?: { ran?: boolean; summary?: string; reason?: string } | null;
};

export type UnreadableDoc = { name: string; ids: string[] };

export type NextStepKind =
  | "ask_docs"
  | "paid"
  | "offer"
  | "discuss"
  | "clarify"
  | "fix_files"
  | "proceed";

export type CheckView = {
  kit: {
    files: number;
    unique: number;
    duplicates: number;
    types: string[];
    missing: string[];
    hasCore: boolean;
  };
  read: {
    total: number;
    textOk: number;
    unreadable: string[];
    unreadableDocs: UnreadableDoc[];
    manual: string[];
  };
  findings: {
    docs: CheckBriefItem[];
    questionnaire: CheckBriefItem[];
    client: CheckBriefItem[];
  };
  /** Автосверка трудовой с ИЛС: ran=false — не проводилась (reason — почему). */
  compare: { ran: boolean; summary: string; reason: string };
  next: { kind: NextStepKind; title: string; text: string };
};

const TYPE_RU: Record<string, string> = {
  ils: "выписка ИЛС",
  workbook: "трудовая книжка",
  labor: "трудовая книжка",
  archive: "архивная справка",
  sfr: "ответ СФР",
};

const TYPE_ORDER = ["выписка ИЛС", "трудовая книжка", "архивная справка", "ответ СФР"];

function typesRu(raw: string[]): string[] {
  const out: string[] = [];
  for (const t of raw) {
    const label = TYPE_RU[t] ?? "прочее";
    if (!out.includes(label)) out.push(label);
  }
  const rank = (s: string) => {
    const i = TYPE_ORDER.indexOf(s);
    return i >= 0 ? i : s === "прочее" ? 99 : 50;
  };
  return out.sort((a, b) => rank(a) - rank(b));
}

function nextStep(
  view: Omit<CheckView, "next">,
  opts: { offerAllowed: boolean; diagPaid: boolean; diagAmountRub?: number },
): CheckView["next"] {
  const amount = `${(opts.diagAmountRub ?? 3000).toLocaleString("ru-RU")} ₽`;
  if (view.kit.missing.length > 0) {
    return {
      kind: "ask_docs",
      title: "Запросите недостающие документы",
      text: `Для сверки стажа не хватает: ${view.kit.missing.join(", ")}. Отправьте клиенту шаблон запроса из ступени «Документы» — как только файл придёт, повторите проверку, и дело сразу двинется дальше.`,
    };
  }
  if (view.findings.docs.length > 0) {
    if (opts.diagPaid) {
      return {
        kind: "paid",
        title: "Диагностика оплачена — готовьте разбор",
        text: "В документах есть конкретные расхождения, и клиент уже оплатил подробный разбор. Откройте ступень «Подробный анализ» и подготовьте письменный результат по отмеченным периодам: что подтверждается документами и что нужно запросить.",
      };
    }
    if (opts.offerAllowed) {
      return {
        kind: "offer",
        title: "Предложите подробную диагностику",
        text: `Краткая сверка уже показала расхождения. Подставьте резюме в чат — там краткий итог и следующий платный шаг: подробный разбор за ${amount} или подготовка обращений. Опирайтесь на документы: клиент часто не может сам назвать причину расхождений.`,
      };
    }
    return {
      kind: "discuss",
      title: "Сообщите итог сверки по документам",
      text: "Документы уже показывают расхождения, счёт на диагностику сейчас не предлагаем. Подставьте резюме — краткий итог по сверке, без опроса мнения клиента. Если не хватает архивных справок или страниц трудовой — попросите именно эти бумаги в чат.",
    };
  }
  if (view.compare.ran) {
    return {
      kind: "proceed",
      title: "Сверка трудовой с ИЛС: расхождений нет",
      text: "Периоды трудовой книжки есть в выписке ИЛС, северные отметки совпадают. Подставьте резюме в чат — клиент получит итог сверки без лишних вопросов. Если клиент пришлёт другие документы (архивные справки), повторите проверку.",
    };
  }
  if (view.findings.questionnaire.length > 0 || view.findings.client.length > 0) {
    return {
      kind: "clarify",
      title: "Запросите документы для сверки",
      text: "Пока есть только темы из анкеты и со слов клиента — это не вывод. Попросите выписку ИЛС с Госуслуг (PDF) и трудовую книжку или справки о стаже прямо в чат. Анализ делаем по документам, а не по оценке клиента «на глаз».",
    };
  }
  if (view.read.unreadable.length > 0) {
    return {
      kind: "fix_files",
      title: "Попросите читаемую версию файла",
      text: `Не прочитан файл: ${view.read.unreadable.join(", ")}. Обычно это фото или скан без текста. Попросите клиента прислать PDF с Госуслуг или более чёткое фото — остальные документы уже можно смотреть.`,
    };
  }
  return {
    kind: "proceed",
    title: "Комплект готов — переходите к сверке",
    text: "Документы на месте и читаются, спорных тем нет. Следующий шаг — сверка сведений: сопоставьте периоды выписки ИЛС с трудовой книжкой.",
  };
}

export function buildCheckView(
  r: CheckResultInput,
  opts: { offerAllowed: boolean; diagPaid: boolean; diagAmountRub?: number },
): CheckView {
  const files = Number(r.documents_checked ?? 0);
  const unique = Number(r.unique_documents ?? files);
  const types = typesRu(r.types_found ?? []);
  const missing = (r.missing_for_task ?? []).filter(Boolean);
  const hasCore =
    missing.length === 0 &&
    types.includes("выписка ИЛС") &&
    types.includes("трудовая книжка");
  const items = r.honest_brief?.items ?? [];
  const unreadableDocs: UnreadableDoc[] = (r.unreadable_docs ?? [])
    .map((d) => ({
      name: String(d.filename || "").trim() || "файл",
      ids: (d.document_ids ?? []).map((id) => String(id || "").trim()).filter(Boolean),
    }))
    .filter((d) => d.ids.length > 0);
  const unreadable =
    unreadableDocs.length > 0
      ? unreadableDocs.map((d) => d.name)
      : (r.unreadable_files ?? []);
  // Без повторов: имена нечитаемых уже уникальны; старые результаты без списка — как есть.
  const dedupedRead = unique < files && r.unreadable_files !== undefined;
  const base: Omit<CheckView, "next"> = {
    kit: { files, unique, duplicates: Math.max(0, files - unique), types, missing, hasCore },
    read: {
      total: dedupedRead ? unique : files,
      textOk: dedupedRead
        ? Math.max(0, unique - unreadable.length)
        : Number(r.text_extracted ?? 0),
      unreadable,
      unreadableDocs,
      manual: r.manual_files ?? [],
    },
    findings: {
      docs: items.filter((i) => i.evidence === "docs"),
      questionnaire: items.filter((i) => i.evidence === "needs_check"),
      client: items.filter((i) => i.evidence === "client"),
    },
    compare: {
      ran: Boolean(r.stazh_compare?.ran),
      summary: r.stazh_compare?.summary ?? "",
      reason: r.stazh_compare?.ran ? "" : (r.stazh_compare?.reason ?? ""),
    },
  };
  return { ...base, next: nextStep(base, opts) };
}
