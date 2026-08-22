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
  ACCOMP: "Подготовка документов / сопровождение",
  SF_LUMP: "Вознаграждение (ЕДВ)",
  SF_MONTH: "Вознаграждение (прибавка × 3 мес.)",
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
  operator: "Оператор",
  expert: "Эксперт",
  admin: "Администратор",
};

export const AUTHOR_KIND_LABELS: Record<string, string> = {
  client: "Клиент",
  representative: "Представитель",
  system: "Система",
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
  draft: "черновик",
  verified: "проверено",
  template: "шаблон",
  rejected: "отклонено",
};

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
  return ORDER_STATUS_LABELS[value] ?? value;
}

export function labelPaymentStatus(value: string): string {
  return PAYMENT_STATUS_LABELS[value] ?? value;
}

export function labelStaffRole(value: string): string {
  return STAFF_ROLE_LABELS[value] ?? value;
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
