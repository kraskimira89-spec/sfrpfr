/** Человекочитаемые ошибки staff API (вместо max_send_failed:HTTPStatusError). */

const CODE_MESSAGES: Record<string, string> = {
  max_send_failed:
    "Не удалось отправить сообщение в MAX. Проверьте связь клиента с ботом и повторите.",
  client_has_no_max_user_id:
    "У клиента нет привязки MAX — отправка недоступна.",
  empty_message: "Введите текст сообщения перед отправкой.",
  duplicate_message: "Это сообщение уже отправлялось. Отправка отменена.",
  duplicate_message_limit:
    "Одинаковое сообщение уже отправлялось слишком часто. Измените текст или подтвердите повтор.",
  "document blocked by antivirus":
    "Файл заблокирован антивирусом — открытие недоступно.",
  "document not available yet":
    "Файл ещё недоступен для открытия. Дождитесь проверки или перезагрузки.",
  "local file missing":
    "Локальная копия файла не найдена на сервере. Нужна повторная загрузка.",
};

export function humanizeStaffApiError(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "Произошла ошибка. Повторите действие.";

  const codeOnly = text.split(":")[0]?.trim() || text;
  if (CODE_MESSAGES[codeOnly]) {
    const suffix = text.includes(":") ? text.slice(text.indexOf(":") + 1).trim() : "";
    // Технические имена исключений (HTTPStatusError) не показываем сотруднику.
    if (!suffix || /^[A-Za-z][A-Za-z0-9_.]*Error$/.test(suffix) || suffix === "Exception") {
      return CODE_MESSAGES[codeOnly];
    }
    return `${CODE_MESSAGES[codeOnly]} (${suffix})`;
  }

  if (/max_send_failed/i.test(text)) {
    return CODE_MESSAGES.max_send_failed;
  }
  if (/HTTPStatusError/i.test(text) && /max/i.test(text)) {
    return CODE_MESSAGES.max_send_failed;
  }

  return text;
}
