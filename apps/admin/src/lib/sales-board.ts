/** Канбан воронки 3/5/8 тыс. в реестре staff (ТЗ-33). */

export const LOSS_REASON_VALUES = [
  "нецелевой вопрос",
  "нет связи",
  "не готов передавать документы",
  "цена",
  "хочет гарантию результата",
  "нет необходимых исходных документов",
  "выбрал самостоятельный путь",
  "выбрал другого исполнителя",
  "неудобен канал",
  "другое",
] as const;

export type LossReason = (typeof LOSS_REASON_VALUES)[number];

export const SALES_BOARD_COLUMNS: Array<{ id: string; label: string }> = [
  { id: "new", label: "Новый лид" },
  { id: "qualify", label: "Квалификация" },
  { id: "docs_collect", label: "Сбор документов" },
  { id: "pay_diag", label: "Оплата 3 000" },
  { id: "diag_work", label: "Диагностика" },
  { id: "diag_done", label: "Результат выдан" },
  { id: "pay_docs", label: "Оплата 5 000" },
  { id: "docs_work", label: "Подготовка документов" },
  { id: "pay_support", label: "Оплата 8 000" },
  { id: "support", label: "Сопровождение" },
  { id: "delivery", label: "Подача клиентом" },
  { id: "closed", label: "Закрыто" },
  { id: "lost", label: "Отказ" },
];

export function salesBoardColumn(input: {
  pipeline_status?: string | null;
  b2c_status?: string | null;
  waiting_on?: string | null;
  finance_attention?: string | null;
  loss_reason?: string | null;
  sales_board_column?: string | null;
}): string {
  if (input.sales_board_column) return input.sales_board_column;
  const p = String(input.pipeline_status || "").toLowerCase();
  const b = String(input.b2c_status || "").toLowerCase();
  const w = String(input.waiting_on || "").toLowerCase();
  const fin = String(input.finance_attention || "").toLowerCase();
  const loss = String(input.loss_reason || "").trim();

  if (b === "closed" || p === "completed" || p === "failed") {
    return loss ? "lost" : "closed";
  }
  if (b === "awaiting_client_submission" || w === "sfr") return "delivery";
  if (fin === "payable" || fin === "awaiting_invoice" || w === "payment" || b === "success_fee_due") {
    return "pay_diag";
  }
  if (w === "client" || w === "archive" || p === "documents_received") {
    return "docs_collect";
  }
  if (
    b === "result_pending" ||
    p === "draft_ready" ||
    p === "human_review" ||
    p === "audited"
  ) {
    return "docs_work";
  }
  if (p === "intake" || b === "lead" || b === "") {
    return "new";
  }
  return "qualify";
}
