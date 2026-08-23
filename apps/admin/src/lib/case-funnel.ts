/** Воронка карточки дела: этапы и текущий фокус. */

export type FunnelStageId =
  | "contact"
  | "documents"
  | "diagnostics"
  | "plan"
  | "payment"
  | "result"
  | "feedback";

export type FunnelStageState = "done" | "current" | "waiting" | "blocked" | "overdue" | "todo";

export type FunnelStage = {
  id: FunnelStageId;
  label: string;
  state: FunnelStageState;
  reason: string;
  canAct: boolean;
};

function checklistDone(
  items: { title?: string; status?: string; item_type?: string }[],
  needle: RegExp,
): boolean {
  const matched = items.filter((i) => needle.test(String(i.title || "")));
  if (matched.length === 0) return false;
  return matched.every((i) => i.status === "done");
}

function hasDocType(
  docs: { doc_type?: string | null; storage_path?: string }[],
  needles: string[],
): boolean {
  return docs.some((d) => {
    const t = `${d.doc_type || ""} ${d.storage_path || ""}`.toLowerCase();
    return needles.some((n) => t.includes(n));
  });
}

function isOverdue(nextActionAt?: string | null): boolean {
  if (!nextActionAt) return false;
  const due = new Date(nextActionAt);
  if (Number.isNaN(due.getTime())) return false;
  return due.getTime() < Date.now();
}

export function deriveFunnel(detail: {
  pipeline_status: string;
  b2c_status: string;
  consent_accepted?: boolean;
  next_action_at?: string | null;
  waiting_on?: string | null;
  client: { max_linked?: boolean; web_linked?: boolean };
  documents: { doc_type?: string | null; storage_path?: string; created_at?: string }[];
  checklist_items: { title?: string; status?: string; item_type?: string }[];
  findings?: unknown[];
  analysis_notes?: string | null;
  draft?: { title?: string; body?: string } | null;
  orders?: { status?: string }[];
  orders_summary?: { status?: string }[];
  audit?: { action: string; at?: string }[];
}): {
  stages: FunnelStage[];
  current: FunnelStageId;
  docsReady: boolean;
  docsRequiredOk: boolean;
  hasIls: boolean;
  hasLabor: boolean;
  consentOk: boolean;
  channelOk: boolean;
  diagnosticsDone: boolean;
  serviceConsentOk: boolean;
  missingDocs: string[];
} {
  const consentOk = Boolean(detail.consent_accepted) || detail.b2c_status !== "lead";
  const channelOk = Boolean(detail.client.max_linked || detail.client.web_linked);
  const items = detail.checklist_items || [];
  const docs = detail.documents || [];
  const hasIls =
    hasDocType(docs, ["ils", "илс", "сзи"]) || checklistDone(items, /илс|выписк/i);
  const hasLabor =
    hasDocType(docs, ["labor", "труд", "employment"]) ||
    checklistDone(items, /труд|стаж/i);
  const docsReady =
    docs.length > 0 ||
    ["documents_received", "ocr_done", "classified", "extracted", "audited", "draft_ready", "human_review", "completed"].includes(
      detail.pipeline_status,
    );
  const docsRequiredOk = hasIls && hasLabor;
  const missingDocs: string[] = [];
  if (!hasIls) missingDocs.push("выписка ИЛС");
  if (!hasLabor) missingDocs.push("трудовая / сведения о стаже");

  const hasDiagnosisReport = hasDocType(docs, ["diagnosis_report", "диагностик"]);
  const diagnosticsDone = Boolean(
    hasDiagnosisReport ||
      detail.analysis_notes ||
      (detail.findings && detail.findings.length > 0) ||
      ["audited", "draft_ready", "human_review", "completed"].includes(detail.pipeline_status),
  );
  const planDone = Boolean(
    detail.draft?.body ||
      ["draft_ready", "human_review", "completed"].includes(detail.pipeline_status) ||
      ["package_delivered", "awaiting_client_submission", "result_pending", "result_confirmed"].includes(
        detail.b2c_status,
      ),
  );
  const orders = detail.orders || detail.orders_summary || [];
  const paymentDone = orders.some((o) =>
    ["paid", "succeeded"].includes(String(o.status || "")),
  );
  const resultDone = ["result_confirmed", "success_fee_due", "success_fee_paid", "closed"].includes(
    detail.b2c_status,
  );
  const feedbackDone = detail.b2c_status === "closed";

  const audit = detail.audit || [];
  const serviceConsentOk =
    detail.b2c_status !== "lead" ||
    audit.some((a) => a.action === "service_consent_recorded");

  let current: FunnelStageId = "contact";
  if (!channelOk || !consentOk) current = "contact";
  else if (!docsReady || (!hasIls && !hasLabor && docs.length === 0)) current = "documents";
  else if (!diagnosticsDone) current = "diagnostics";
  else if (!planDone) current = "plan";
  else if (!paymentDone && detail.b2c_status !== "lead") current = "payment";
  else if (!resultDone) current = "result";
  else current = "feedback";

  const order: FunnelStageId[] = [
    "contact",
    "documents",
    "diagnostics",
    "plan",
    "payment",
    "result",
    "feedback",
  ];
  const doneFlags: Record<FunnelStageId, boolean> = {
    contact: channelOk && consentOk,
    documents: docsReady && (hasIls || hasLabor || docs.length > 0),
    diagnostics: diagnosticsDone,
    plan: planDone,
    payment: paymentDone,
    result: resultDone,
    feedback: feedbackDone,
  };
  const labels: Record<FunnelStageId, string> = {
    contact: "Контакт и согласие",
    documents: "Документы",
    diagnostics: "Диагностика",
    plan: "План / обращение",
    payment: "Оплата",
    result: "Ответ СФР",
    feedback: "База знаний",
  };

  const wait = detail.waiting_on || "";
  const overdue = isOverdue(detail.next_action_at);

  const stages: FunnelStage[] = order.map((id) => {
    const idx = order.indexOf(id);
    const curIdx = order.indexOf(current);
    let state: FunnelStageState = "todo";
    let reason = "";
    let canAct = false;

    if (id === current) {
      state = overdue ? "overdue" : "current";
      canAct = true;
      if (id === "documents" && !docsRequiredOk) {
        reason = `Не хватает: ${missingDocs.join(", ")}`;
      } else if (id === "diagnostics" && !docsRequiredOk) {
        state = "blocked";
        canAct = false;
        reason = `Для диагностики не хватает: ${missingDocs.join(", ")}`;
      } else if (id === "plan" && !diagnosticsDone) {
        state = "blocked";
        canAct = false;
        reason = "Сначала завершите диагностику";
      } else if (id === "payment" && !serviceConsentOk) {
        state = "blocked";
        canAct = false;
        reason = "Сначала зафиксируйте согласие клиента на услугу";
      } else if (wait === "client" || wait === "archive" || wait === "sfr" || wait === "payment") {
        state = overdue ? "overdue" : "waiting";
        reason =
          wait === "client"
            ? "Ждём клиента"
            : wait === "archive"
              ? "Ждём архив"
              : wait === "sfr"
                ? "Ждём ответ СФР"
                : "Ждём оплату";
      } else {
        reason = overdue ? "Срок просрочен" : "Текущий этап — можно действовать";
      }
    } else if (doneFlags[id] || idx < curIdx) {
      state = "done";
      reason = "Этап завершён";
      canAct = false;
    } else {
      state = "todo";
      canAct = false;
      if (id === "plan" && !diagnosticsDone) {
        state = "blocked";
        reason = "Доступно после диагностики";
      } else if (id === "payment" && !serviceConsentOk) {
        state = "blocked";
        reason = "Нужно согласие на услугу";
      } else if (id === "diagnostics" && !docsRequiredOk) {
        state = "blocked";
        reason = `Не хватает: ${missingDocs.join(", ")}`;
      } else {
        reason = "Ещё не наступил";
      }
    }

    return { id, label: labels[id], state, reason, canAct };
  });

  return {
    stages,
    current,
    docsReady,
    docsRequiredOk,
    hasIls,
    hasLabor,
    consentOk,
    channelOk,
    diagnosticsDone,
    serviceConsentOk,
    missingDocs,
  };
}

export function primaryCtaLabel(current: FunnelStageId, docsReady: boolean): string {
  if (current === "contact") return "Настроить канал связи";
  if (current === "documents") return docsReady ? "Запустить проверку" : "Запросить документы";
  if (current === "diagnostics") return "Запустить проверку";
  if (current === "plan") return "Сформировать проект";
  if (current === "payment") return "Создать счёт";
  if (current === "result") return "Зафиксировать ответ СФР";
  return "Сохранить в базу знаний";
}

export function slaHint(detail: {
  waiting_on?: string | null;
  next_action_at?: string | null;
}): string {
  const wait = detail.waiting_on || "";
  if (wait === "client") return "Ждём клиента";
  if (wait === "archive") return "Ждём архив";
  if (wait === "sfr") return "Ждём ответ СФР";
  if (wait === "payment") return "Ждём оплату";
  if (detail.next_action_at) {
    const due = new Date(detail.next_action_at);
    if (!Number.isNaN(due.getTime())) {
      const diffH = (due.getTime() - Date.now()) / 36e5;
      if (diffH < 0)
        return `Просрочено с ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
      if (diffH < 24)
        return `Срок сегодня ${due.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
      return `Срок ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
    }
  }
  if (wait === "staff") return "Ответить в приоритете";
  return "Срок не задан";
}

export const DOC_REQUEST_ILS =
  "Здравствуйте! Для проверки нужна выписка ИЛС с Госуслуг. Загрузите файл только в личном кабинете — не в этот чат. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const DOC_REQUEST_LABOR =
  "Здравствуйте! Подготовьте трудовую книжку или сведения о стаже и загрузите в личный кабинет (не в MAX). Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const SERVICE_DESCRIPTION_CHAT =
  "Здравствуйте! Кратко об услуге: мы готовим документы, проект обращения и понятный план. Подаёте через СФР, МФЦ или Госуслуги вы сами — решение принимает только СФР. Если согласны продолжить — напишите, и оформим следующий шаг.";

export const PLAN_READY_CHAT =
  "Диагностика готова и доступна в защищённом кабинете. В документе выделены: что проверено, какие вопросы требуют уточнения и какой следующий шаг рекомендуем.\n\nПосле ознакомления напишите, пожалуйста, одним сообщением:\n1 — всё понятно\n2 — нужна помощь разобраться с планом\n3 — есть вопрос по документу";
