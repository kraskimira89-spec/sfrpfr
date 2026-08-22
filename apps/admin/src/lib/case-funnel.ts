/** Воронка карточки дела: этапы и текущий фокус. */

export type FunnelStageId =
  | "contact"
  | "documents"
  | "diagnostics"
  | "plan"
  | "payment"
  | "result"
  | "feedback";

export type FunnelStageState = "done" | "current" | "todo";

export type FunnelStage = {
  id: FunnelStageId;
  label: string;
  state: FunnelStageState;
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

export function deriveFunnel(detail: {
  pipeline_status: string;
  b2c_status: string;
  consent_accepted?: boolean;
  client: { max_linked?: boolean; web_linked?: boolean };
  documents: { doc_type?: string | null; storage_path?: string }[];
  checklist_items: { title?: string; status?: string; item_type?: string }[];
  findings?: unknown[];
  analysis_notes?: string | null;
  draft?: { title?: string; body?: string } | null;
  orders?: { status?: string }[];
  orders_summary?: { status?: string }[];
}): {
  stages: FunnelStage[];
  current: FunnelStageId;
  docsReady: boolean;
  hasIls: boolean;
  hasLabor: boolean;
  consentOk: boolean;
  channelOk: boolean;
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
  const diagnosticsDone = Boolean(
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
  const stages: FunnelStage[] = order.map((id) => {
    let state: FunnelStageState = "todo";
    if (id === current) state = "current";
    else if (doneFlags[id]) state = "done";
    else {
      const idx = order.indexOf(id);
      const curIdx = order.indexOf(current);
      if (idx < curIdx) state = "done";
    }
    return { id, label: labels[id], state };
  });

  return {
    stages,
    current,
    docsReady,
    hasIls,
    hasLabor,
    consentOk,
    channelOk,
  };
}

export function primaryCtaLabel(current: FunnelStageId, docsReady: boolean): string {
  if (current === "contact") return "Настроить контакт";
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
      if (diffH < 0) return `Просрочено с ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
      if (diffH < 24) return `Срок сегодня ${due.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
      return `Срок ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
    }
  }
  if (wait === "staff") return "Ответить в приоритете";
  return "Срок не задан";
}
