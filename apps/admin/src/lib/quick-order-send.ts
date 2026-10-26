/** Текст уведомления после create + pay-link(send_max). */
export function noticeAfterQuickOrderSend(sent: boolean): string {
  return sent
    ? "Счёт создан и отправлен клиенту в MAX (текст, кнопка и QR)."
    : "Счёт создан, ссылка готова, но MAX не отправлен (проверьте привязку клиента).";
}
