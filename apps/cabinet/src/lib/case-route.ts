/** Клиентские главы маршрута поверх work.stages / status_key (без нового backend). */

export type RouteChapterId =
  | "intro"
  | "documents"
  | "review"
  | "plan"
  | "outcome";

export type RouteChapter = {
  id: RouteChapterId;
  label: string;
  state: "done" | "current" | "todo";
};

export type RouteDocMark = {
  key: string;
  title: string;
  mark: "done" | "need" | "checking" | "fix" | "optional";
  statusText: string;
  purpose?: string;
};

export type RouteNextStep = {
  mode: "action" | "waiting";
  title: string;
  why: string;
  primaryLabel: string | null;
  howtoUrl: string | null;
  howtoLabel: string | null;
  /** Только для документного CTA (upload). */
  showCantGetDocument: boolean;
  /** Только там, где сохранение файлов действительно работает. */
  showContinueLaterHint: boolean;
  /** Пояснение последствий (договор / оплата). */
  consequenceHint: string | null;
  helpLabel: string;
};

export type RouteAddedDoc = {
  when: string;
  text: string;
};

export type RoutePrimaryAction =
  | { kind: "consent" }
  | { kind: "contract" }
  | { kind: "pay"; orderId: string }
  | { kind: "upload"; slotKey: string }
  | { kind: "result"; documentId: string }
  | { kind: "unavailable"; reason: string }
  | { kind: "none" };

export type ClientWorkLike = {
  status_key: string;
  status_label: string;
  status_hint: string;
  now_need: string;
  cta_key: string;
  cta_label: string;
  consent_ok?: boolean;
  required_uploaded: number;
  required_total: number;
  stages: { n: number; title: string; hint: string; state: string }[];
  documents: {
    key: string;
    title: string;
    need: string;
    status: string;
    status_label: string;
    added_at?: string | null;
    doc_type?: string | null;
  }[];
  next_actions: string[];
  ils_howto_url: string;
  order?: {
    amount_rub?: number;
    order_id?: string | null;
    title?: string;
  };
  result?: {
    ready?: boolean;
    document_id?: string | null;
  };
};

const CHAPTER_META: { id: RouteChapterId; label: string; stageN: number }[] = [
  { id: "intro", label: "Знакомство", stageN: 1 },
  { id: "documents", label: "Документы", stageN: 2 },
  { id: "review", label: "Проверка", stageN: 3 },
  { id: "plan", label: "План действий", stageN: 4 },
  { id: "outcome", label: "Итоги", stageN: 5 },
];

const DOC_PURPOSE: Record<string, string> = {
  ils: "Нужна, чтобы сопоставить периоды работы и сведения о пенсионных правах.",
  labor: "Нужна для построчной сверки с выпиской о состоянии лицевого счёта.",
  archive: "Подтверждает периоды, если организация уже не существует.",
  passport: "Для сверки установочных данных, если специалист попросит.",
};

export function chaptersFromWork(work: ClientWorkLike): RouteChapter[] {
  const byN = new Map(work.stages.map((s) => [s.n, s]));
  return CHAPTER_META.map((meta) => {
    const stage = byN.get(meta.stageN);
    const state =
      stage?.state === "done" || stage?.state === "current" || stage?.state === "todo"
        ? stage.state
        : "todo";
    return { id: meta.id, label: meta.label, state };
  });
}

export function currentChapterId(work: ClientWorkLike): RouteChapterId {
  const chapters = chaptersFromWork(work);
  const current = chapters.find((c) => c.state === "current");
  if (current) return current.id;
  if (work.status_key === "consent") return "intro";
  if (work.status_key === "waiting_docs" || work.status_key === "need_info") return "documents";
  if (work.status_key === "docs_review" || work.status_key === "diagnosis") return "review";
  if (work.status_key === "result_ready") return "plan";
  if (work.status_key === "done") return "outcome";
  return "documents";
}

export function chapterTitle(id: RouteChapterId): { heading: string; lead: string } {
  switch (id) {
    case "intro":
      return {
        heading: "Знакомство",
        lead: "Сохраним необходимые сведения и согласие, чтобы можно было работать с документами.",
      };
    case "documents":
      return {
        heading: "Собираем документы",
        lead: "Подготовим сведения для проверки вашего стажа.",
      };
    case "review":
      return {
        heading: "Разбираемся в стаже",
        lead: "Специалист проверяет комплект. От вас сейчас может ничего не требоваться.",
      };
    case "plan":
      return {
        heading: "Готовим следующие действия",
        lead: "Посмотрите итог проверки и предложенный план.",
      };
    case "outcome":
      return {
        heading: "Подводим итоги",
        lead: "Зафиксирован результат работы по документам. Решение о пенсии принимает СФР.",
      };
  }
}

export function firstUploadSlot(work: ClientWorkLike) {
  return (
    work.documents.find(
      (row) => row.need === "required" && (row.status === "missing" || row.status === "reupload"),
    ) ||
    work.documents.find((row) => row.status === "reupload") ||
    null
  );
}

function formatRub(amount: number | undefined): string {
  const n = Number(amount || 0);
  return n.toLocaleString("ru-RU");
}

/** Явное сопоставление cta_key → действие. Без fallback на загрузку. */
export function resolveRoutePrimaryAction(
  work: ClientWorkLike,
  opts?: { hasContractHandler?: boolean },
): RoutePrimaryAction {
  const cta = work.cta_key;
  if (cta === "wait") return { kind: "none" };

  if (cta === "consent") {
    if (work.consent_ok) {
      return { kind: "unavailable", reason: "Согласие уже сохранено. Обновите страницу, если шаг не сменился." };
    }
    return { kind: "consent" };
  }

  if (cta === "contract") {
    if (!opts?.hasContractHandler) {
      return {
        kind: "unavailable",
        reason: "Сейчас нельзя принять условия. Обновите страницу или напишите в чат.",
      };
    }
    return { kind: "contract" };
  }

  if (cta === "pay") {
    const orderId = work.order?.order_id;
    if (!orderId) {
      return {
        kind: "unavailable",
        reason: "Счёт ещё не готов или недоступен. Обновите страницу или напишите в чат.",
      };
    }
    return { kind: "pay", orderId };
  }

  if (cta === "result" || cta === "done") {
    const documentId = work.result?.document_id;
    if (!documentId) {
      return {
        kind: "unavailable",
        reason: "Файл результата пока недоступен. Обновите страницу чуть позже или напишите в чат.",
      };
    }
    return { kind: "result", documentId };
  }

  if (cta === "upload") {
    const slot = firstUploadSlot(work);
    if (!slot) {
      return {
        kind: "unavailable",
        reason: "Сейчас нет документа для загрузки. Обновите страницу или напишите в чат.",
      };
    }
    return { kind: "upload", slotKey: slot.key };
  }

  return {
    kind: "unavailable",
    reason: "Действие временно недоступно. Обновите страницу или напишите в чат.",
  };
}

export function nextStepFromWork(work: ClientWorkLike): RouteNextStep {
  const cta = work.cta_key;

  if (cta === "wait") {
    return {
      mode: "waiting",
      title: "Сейчас работает специалист",
      why: "От вас ничего не требуется. Дополнительные документы пока не нужны.",
      primaryLabel: null,
      howtoUrl: null,
      howtoLabel: null,
      showCantGetDocument: false,
      showContinueLaterHint: false,
      consequenceHint: null,
      helpLabel: "Задать вопрос",
    };
  }

  if (cta === "consent") {
    return {
      mode: "action",
      title: work.now_need,
      why: "Без согласия нельзя загружать файлы и продолжать работу с делом в кабинете.",
      primaryLabel: work.cta_label,
      howtoUrl: null,
      howtoLabel: null,
      showCantGetDocument: false,
      showContinueLaterHint: false,
      consequenceHint: null,
      helpLabel: "Нужна помощь",
    };
  }

  if (cta === "contract") {
    const amount = formatRub(work.order?.amount_rub);
    return {
      mode: "action",
      title: work.now_need,
      why: "После принятия условий будет сформирован счёт на диагностику.",
      primaryLabel: work.cta_label,
      howtoUrl: null,
      howtoLabel: null,
      showCantGetDocument: false,
      showContinueLaterHint: false,
      consequenceHint: `После принятия условий будет сформирован счёт на диагностику — ${amount} ₽. Оплатить можно будет сразу здесь же.`,
      helpLabel: "Нужна помощь",
    };
  }

  if (cta === "pay") {
    const amount = formatRub(work.order?.amount_rub);
    return {
      mode: "action",
      title: work.now_need,
      why: "Оплата проходит через защищённую ссылку. Это не подача заявления в СФР.",
      primaryLabel: work.cta_label,
      howtoUrl: null,
      howtoLabel: null,
      showCantGetDocument: false,
      showContinueLaterHint: false,
      consequenceHint: `К оплате: ${amount} ₽. Оплата счёта означает принятие условий публичной оферты.`,
      helpLabel: "Задать вопрос об услуге",
    };
  }

  if (cta === "result" || cta === "done") {
    return {
      mode: "action",
      title: work.now_need,
      why: "Откройте итог проверки документов. Решение о пенсии принимает только СФР.",
      primaryLabel: work.cta_label,
      howtoUrl: null,
      howtoLabel: null,
      showCantGetDocument: false,
      showContinueLaterHint: false,
      consequenceHint: null,
      helpLabel: "Задать вопрос",
    };
  }

  if (cta === "upload") {
    const slot = firstUploadSlot(work);
    const why =
      (slot && DOC_PURPOSE[slot.key]) ||
      work.status_hint ||
      "Это поможет специалисту продолжить проверку.";
    let howtoUrl: string | null = null;
    let howtoLabel: string | null = null;
    if (slot?.key === "ils" || /илс|выписк/i.test(`${work.now_need} ${slot?.title || ""}`)) {
      howtoUrl = work.ils_howto_url;
      howtoLabel = "Где получить документ?";
    }
    return {
      mode: "action",
      title: work.now_need,
      why,
      primaryLabel: work.cta_label,
      howtoUrl,
      howtoLabel,
      showCantGetDocument: true,
      showContinueLaterHint: true,
      consequenceHint: null,
      helpLabel: "Нужна помощь",
    };
  }

  // Неизвестный CTA — без документных подсказок и без обещания сохранения файлов.
  return {
    mode: "action",
    title: work.now_need || "Действие временно недоступно",
    why: "Обновите страницу или напишите в чат. Сейчас нельзя безопасно продолжить этот шаг.",
    primaryLabel: null,
    howtoUrl: null,
    howtoLabel: null,
    showCantGetDocument: false,
    showContinueLaterHint: false,
    consequenceHint: null,
    helpLabel: "Нужна помощь",
  };
}

export function kitMarksFromWork(work: ClientWorkLike): RouteDocMark[] {
  const visible = work.documents.filter((row) => {
    if (row.need === "required") return true;
    if (row.status === "reupload" || row.status === "awaiting" || row.status === "accepted") {
      return true;
    }
    if (row.status === "staff_requested") return true;
    return false;
  });

  return visible.map((row) => {
    let mark: RouteDocMark["mark"] = "optional";
    if (row.status === "accepted") mark = "done";
    else if (row.status === "awaiting") mark = "checking";
    else if (row.status === "reupload") mark = "fix";
    else if (row.status === "missing" && row.need === "required") mark = "need";
    else if (row.status === "staff_requested") mark = "need";

    let statusText = row.status_label;
    if (row.status === "awaiting") {
      statusText = "Документ получен. Проверим его пригодность";
    } else if (row.status === "accepted") {
      statusText = "Принят для текущего этапа";
    }

    return {
      key: row.key,
      title: row.title,
      mark,
      statusText,
      purpose: DOC_PURPOSE[row.key],
    };
  });
}

/**
 * Только подтверждённый факт загрузки. Не выдаёт added_at за дату проверки/замены.
 * Без машинной даты сортировки — это не хронологическая лента событий.
 */
export function addedDocumentsFromWork(work: ClientWorkLike, limit = 5): RouteAddedDoc[] {
  const rows = work.documents.filter((row) => Boolean(row.added_at));
  return rows.slice(0, limit).map((row) => ({
    when: String(row.added_at),
    text: `Вы добавили документ: ${row.title}`,
  }));
}

/** @deprecated используйте addedDocumentsFromWork */
export function recentEventsFromWork(work: ClientWorkLike, limit = 5): RouteAddedDoc[] {
  return addedDocumentsFromWork(work, limit);
}

export function requiredProgressLabel(work: ClientWorkLike): string | null {
  if (work.required_total <= 0) return null;
  return `Обязательных документов: ${work.required_uploaded} из ${work.required_total}`;
}
