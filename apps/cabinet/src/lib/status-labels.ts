/**
 * Общие RU-лейблы статусов (зеркало shared/status-labels.json + /meta/status-labels).
 * Источник истины на бэкенде: sfrfr.models.case_status.
 */

export type StatusLabelsBundle = {
  labels: Record<string, string>;
  hints: Record<string, string>;
  b2c: Record<string, string>;
  senior: Record<string, string>;
};

const FALLBACK: StatusLabelsBundle = {
  labels: {
    intake: "Приём данных",
    documents_received: "Документы получены",
    ocr_done: "Текст распознан",
    classified: "Документы классифицированы",
    extracted: "Периоды извлечены",
    audited: "Сверка завершена",
    draft_ready: "Черновик готов",
    human_review: "На проверке специалиста",
    completed: "Завершено",
    failed: "Ошибка",
  },
  hints: {
    intake: "Загрузите сканы ИЛС и трудовой книжки.",
    documents_received: "Документы приняты. Можно запустить проверку.",
    ocr_done: "Текст распознан, идёт классификация.",
    classified: "Типы документов определены.",
    extracted: "Периоды собраны, выполняется сверка.",
    audited: "Найдены расхождения — готовим черновик.",
    draft_ready: "Черновик заявления готов к проверке.",
    human_review: "Ждите ответа специалиста.",
    completed: "Дело закрыто.",
    failed: "Произошла ошибка при обработке.",
  },
  b2c: {
    lead: "Заявка",
    consent_accepted: "Согласие принято",
    diagnostic_paid: "Первичная проверка оплачена",
    contract_accepted: "Заказ принят",
    service_paid: "Услуга оплачена",
    package_delivered: "Пакет выдан",
    awaiting_client_submission: "Ожидаем вашу подачу",
    result_pending: "Ждём решение СФР",
    result_confirmed: "Результат подтверждён",
    success_fee_due: "Счёт за результат",
    success_fee_paid: "Вознаграждение оплачено",
    closed: "Закрыто",
  },
  senior: {
    needs_documents: "Нужны документы",
    documents_received: "Документы получены",
    in_review: "Идёт проверка",
    draft_or_expert: "Готов черновик / проверка специалиста",
    needs_help: "Нужна помощь специалиста",
    payment_received: "Оплата получена",
    has_result: "Есть результат",
    completed: "Дело завершено",
  },
};

let cached: StatusLabelsBundle = FALLBACK;

export function getStatusLabels(): StatusLabelsBundle {
  return cached;
}

export async function loadStatusLabels(apiBase: string): Promise<StatusLabelsBundle> {
  try {
    const response = await fetch(`${apiBase}/api/portal/meta/status-labels`);
    if (!response.ok) return cached;
    const data = (await response.json()) as Partial<StatusLabelsBundle>;
    cached = {
      labels: { ...FALLBACK.labels, ...(data.labels || {}) },
      hints: { ...FALLBACK.hints, ...(data.hints || {}) },
      b2c: { ...FALLBACK.b2c, ...(data.b2c || {}) },
      senior: { ...FALLBACK.senior, ...(data.senior || {}) },
    };
  } catch {
    /* keep fallback */
  }
  return cached;
}

export function labelStatus(value: string): string {
  const bundle = getStatusLabels();
  return bundle.labels[value] ?? bundle.b2c[value] ?? value;
}

/** Короткий статус для пенсионера — та же логика, что human_case_status на бэкенде. */
export function humanCaseStatus(pipeline: string, b2c: string): string {
  const p = (pipeline || "").toLowerCase();
  const b = (b2c || "").toLowerCase();
  const s = getStatusLabels().senior;
  if (b.includes("success_fee") || b.includes("result_confirmed")) {
    return s.has_result;
  }
  if (b.includes("service_paid") || b.includes("diagnostic_paid")) {
    return s.payment_received;
  }
  if (p.includes("draft") || p.includes("human_review")) {
    return s.draft_or_expert;
  }
  if (p.includes("failed")) return s.needs_help;
  if (
    p.includes("ocr") ||
    p.includes("classif") ||
    p.includes("extract") ||
    p.includes("audit")
  ) {
    return s.in_review;
  }
  if (p.includes("document") || b.includes("documents")) {
    return s.documents_received;
  }
  if (p.includes("completed") || b.includes("closed")) return s.completed;
  return s.needs_documents;
}
