/**
 * RU-лейблы для кабинетов (клиент / сотрудник / MAX mini-app).
 * Коды в API остаются на английском; в UI показываем перевод.
 */

export const PIPELINE_LABELS: Record<string, string> = {
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
  new: "Новое",
  documents_requested: "Запрошены документы",
};

export const B2C_LABELS: Record<string, string> = {
  lead: "Заявка",
  consent_accepted: "Согласие принято",
  diagnostic_paid: "Диагностика оплачена",
  contract_accepted: "Заказ принят",
  service_paid: "Услуга оплачена",
  package_delivered: "Пакет выдан",
  awaiting_client_submission: "Ожидаем вашу подачу",
  result_pending: "Ждём решение СФР",
  result_confirmed: "Результат подтверждён",
  success_fee_due: "Счёт за результат",
  success_fee_paid: "Вознаграждение оплачено",
  closed: "Закрыто",
};

export const PACKAGE_LABELS: Record<string, string> = {
  DIAG: "Диагностика",
  ACCOMP: "Подготовка документов / обращение",
  SUPPORT: "Сопровождение до подачи",
  SF_LUMP: "Индивидуальное соглашение",
  SF_MONTH: "Индивидуальное соглашение",
};

export const FINANCE_STATUS_LABELS: Record<string, string> = {
  awaiting_invoice: "Ожидает счёт",
  draft: "Черновик",
  invoice_ready: "Счёт подготовлен",
  invoice_sent: "Счёт отправлен",
  pending_payment: "Ожидает оплату",
  pending: "Ожидает оплату",
  awaiting_payment: "Ожидает оплату",
  partially_paid: "Частично оплачено",
  paid: "Оплачено",
  overdue: "Просрочено",
  cancelled: "Отменено",
  canceled: "Отменено",
  refund: "Возврат",
  reconciliation_error: "Ошибка сверки",
};

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: "ожидает оплаты",
  awaiting_payment: "к оплате",
  paid: "оплачено",
  succeeded: "оплачено",
  cancelled: "отменён",
  canceled: "отменён",
  failed: "ошибка оплаты",
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  pending: "в обработке",
  waiting_for_capture: "ожидает подтверждения",
  succeeded: "успешно",
  canceled: "отменён",
  cancelled: "отменён",
};

export const STAFF_ROLE_LABELS: Record<string, string> = {
  operator: "Оператор приёма",
  expert: "Специалист",
  admin: "Администратор",
};

export const STAFF_STATUS_LABELS: Record<string, string> = {
  active: "Активен",
  invited: "Приглашён",
  suspended: "Приостановлен",
  archived: "Архив",
};

export const AUTHOR_KIND_LABELS: Record<string, string> = {
  client: "Клиент",
  representative: "Представитель",
  system: "Бот MAX",
  expert: "Эксперт",
  operator: "Оператор",
  staff: "Сотрудник",
};

export const CHECKLIST_STATUS_LABELS: Record<string, string> = {
  open: "открыт",
  done: "выполнен",
};

export const CHECKLIST_OWNER_LABELS: Record<string, string> = {
  client: "клиент",
  staff: "сотрудник",
  expert: "эксперт",
};

export const FEEDBACK_QUALITY_LABELS: Record<string, string> = {
  draft: "Черновик",
  verified: "Проверено",
  template: "Шаблон",
  rejected: "Отклонено",
};

/** Коды access_audit.action → русский текст (служебный журнал). */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  staff_case_viewed: "Сотрудник открыл дело",
  pipeline_run_requested: "Запрошен запуск проверки",
  pipeline_status_updated: "Обновлён этап маршрута",
  invoice_sent: "Счёт отправлен",
  order_created: "Создан счёт",
  order_cancelled: "Счёт отменён",
  staff_max_reply_sent: "Сообщение отправлено в MAX",
  pay_link_max: "Ссылка на оплату в MAX",
  payment_succeeded: "Оплата прошла",
  payment_created: "Платёж создан",
  payment_reservation_created: "Резерв платежа",
  payment_reminder: "Напоминание об оплате",
  manual_paid: "Оплата отмечена вручную",
  partial_payment: "Частичная оплата",
  receipt_confirmed: "Чек подтверждён",
  service_consent_recorded: "Зафиксировано согласие на услугу",
  consent_accepted: "Согласие принято",
  contract_accepted: "Договор принят",
  case_created: "Дело создано",
  expert_assigned: "Назначен специалист",
  result_confirmed: "Результат подтверждён",
  knowledge_feedback: "Заметка в базу знаний",
  next_action_updated: "Обновлено следующее действие",
  archive_prep_updated: "Обновлена подготовка к архиву",
  checklist_item_created: "Пункт чек-листа создан",
  checklist_item_updated: "Пункт чек-листа обновлён",
  document_deleted_by_staff: "Документ удалён сотрудником",
  document_uploaded: "Документ загружен",
  result_decision_uploaded: "Загружен ответ СФР",
  staff_document_check_requested: "Запущена проверка документов",
  appeal_docx_downloaded: "Скачан DOCX обращения",
  appeal_draft_deleted: "Черновик обращения удалён",
  appeal_draft_replaced: "Черновик обращения заменён",
  analysis_notes_replaced: "Notes пайплайна заменены",
  periods_replaced: "Таблицы периодов обновлены",
  discrepancy_reviewed: "Расхождение просмотрено",
  facts_review_discrepancies: "Сверка: есть расхождения",
  facts_review_no_discrepancies: "Сверка: расхождений нет",
  diagnostic_result_published: "Опубликован результат диагностики",
  marketing_consent_requested: "Запрошено согласие на маркетинг",
  ingest_rerun: "Повторный разбор файла",
  ingest_accept: "Файл принят после разбора",
  ingest_reject: "Файл отклонён после разбора",
  ingest_edit: "Правка после разбора",
  ingest_artifacts_viewed: "Просмотрены артефакты разбора",
  security_manual_approve: "Ручное одобрение безопасности",
  representative_added: "Добавлен представитель",
  representative_removed: "Удалён представитель",
  case_scenarios_updated: "Обновлены сценарии дела",
  secure_view_pdf: "Просмотр PDF по ссылке",
};

export const FEEDBACK_QUALITY_STAGES: readonly string[] = [
  "draft",
  "verified",
  "template",
  "rejected",
];

export function feedbackQualityOptions(): Array<{ value: string; label: string }> {
  return FEEDBACK_QUALITY_STAGES.map((value) => ({
    value,
    label: labelFeedbackQuality(value),
  }));
}

export const PIPELINE_STAGES: readonly string[] = [
  "intake",
  "documents_received",
  "ocr_done",
  "classified",
  "extracted",
  "audited",
  "draft_ready",
  "human_review",
  "completed",
  "failed",
];

export const PIPELINE_FILTER_STAGES: readonly string[] = [
  "intake",
  "documents_received",
  "ocr_done",
  "classified",
  "extracted",
  "audited",
  "draft_ready",
  "human_review",
  "completed",
  "failed",
];

export function pipelineStageOptions(
  stages: readonly string[] = PIPELINE_STAGES,
): Array<{ value: string; label: string }> {
  return stages.map((value) => ({ value, label: labelPipeline(value) }));
}

export function labelPipeline(value: string): string {
  return PIPELINE_LABELS[value] ?? value;
}

export function labelB2c(value: string): string {
  return B2C_LABELS[value] ?? value;
}

export function labelPackage(value: string): string {
  return PACKAGE_LABELS[value] ?? value;
}

export function labelOrderStatus(value: string): string {
  return FINANCE_STATUS_LABELS[value] ?? ORDER_STATUS_LABELS[value] ?? value;
}

export function labelFinanceStatus(value: string): string {
  return FINANCE_STATUS_LABELS[value] ?? labelOrderStatus(value);
}

export function labelPaymentStatus(value: string): string {
  return PAYMENT_STATUS_LABELS[value] ?? value;
}

export function labelStaffRole(value: string): string {
  return STAFF_ROLE_LABELS[value] ?? value;
}

export function labelStaffStatus(value: string): string {
  return STAFF_STATUS_LABELS[value] ?? value;
}

export function labelAuthorKind(value: string): string {
  return AUTHOR_KIND_LABELS[value] ?? value;
}

export function labelChecklistStatus(value: string): string {
  return CHECKLIST_STATUS_LABELS[value] ?? value;
}

export function labelChecklistOwner(value: string): string {
  return CHECKLIST_OWNER_LABELS[value] ?? value;
}

export function labelFeedbackQuality(value: string): string {
  return FEEDBACK_QUALITY_LABELS[value] ?? value;
}

export function formatCaseStatuses(pipeline: string, b2c: string): string {
  return `${labelPipeline(pipeline)} · ${labelB2c(b2c)}`;
}

/** Подпись события журнала; суффикс после «:» — пакет/качество/id. */
export function labelAuditAction(action: string): string {
  const raw = (action || "").trim();
  if (!raw) return "—";
  const colon = raw.indexOf(":");
  const base = colon >= 0 ? raw.slice(0, colon) : raw;
  const rest = colon >= 0 ? raw.slice(colon + 1) : "";
  const baseLabel = AUDIT_ACTION_LABELS[base] ?? AUDIT_ACTION_LABELS[raw] ?? raw;
  if (!rest) return baseLabel;
  if (PACKAGE_LABELS[rest]) return `${baseLabel}: ${PACKAGE_LABELS[rest]}`;
  if (FEEDBACK_QUALITY_LABELS[rest]) return `${baseLabel}: ${FEEDBACK_QUALITY_LABELS[rest]}`;
  if (AUDIT_ACTION_LABELS[raw]) return AUDIT_ACTION_LABELS[raw];
  return `${baseLabel}: ${rest}`;
}

/** Короткий рабочий статус для очереди сотрудника (не сырые коды). */
export function humanCaseStage(pipeline: string, b2c: string): string {
  const p = (pipeline || "").toLowerCase();
  const b = (b2c || "").toLowerCase();
  if (p === "intake" && (b === "lead" || b === "")) return "Новая заявка";
  if (b === "lead") return "Новая заявка";
  if (p === "documents_received") return "Документы";
  if (p === "audited") return "Расхождения";
  if (p === "draft_ready" || p === "human_review") return "Проект обращения";
  if (b === "awaiting_client_submission") return "Ожидаем подачу";
  if (b === "result_pending") return "Ждём СФР";
  if (b === "success_fee_due") return "Ожидаем оплату";
  if (p === "completed" || b === "closed") return "Завершено";
  return labelPipeline(p);
}
