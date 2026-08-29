/** Цветовые индикаторы дел в admin: SLA (полоска) + бейджи ситуации. */

export type SlaTone = "overdue" | "soon" | "today" | "calm" | "ok" | "muted";

export type CaseIndicatorInput = {
  waiting_on?: string | null;
  priority?: string | null;
  deadline_status?: string | null;
  is_test?: boolean;
  pipeline_status?: string | null;
  b2c_status?: string | null;
  expert_user_id?: string | null;
  max_linked?: boolean;
  web_linked?: boolean;
  silent_days?: number;
  consent_accepted?: boolean | null;
  /** Последнее сообщение в чате — от клиента (нужен ответ). */
  chat_awaits_staff?: boolean;
  /** Сигнал финансов: awaiting_invoice | payable (не этап сделки). */
  finance_attention?: "awaiting_invoice" | "payable" | null;
};

export type SituationBadge = {
  id: string;
  label: string;
  kind:
    | "reply"
    | "docs"
    | "payment"
    | "sfr"
    | "consent"
    | "mine"
    | "free"
    | "test"
    | "silent"
    | "max"
    | "web";
  title: string;
};

const EXTERNAL_WAIT = new Set(["client", "archive", "sfr", "payment"]);
const SILENT_THRESHOLD = 3;

export function slaTone(item: CaseIndicatorInput): SlaTone {
  const pipe = String(item.pipeline_status || "");
  const b2c = String(item.b2c_status || "");
  if (
    item.is_test ||
    pipe === "completed" ||
    b2c === "closed" ||
    b2c === "paused"
  ) {
    return "muted";
  }
  const dl = String(item.deadline_status || "");
  const pr = String(item.priority || "");
  if (dl === "overdue" || pr === "urgent") return "overdue";
  if (dl === "soon") return "soon";
  if (dl === "today" || pr === "today") return "today";
  const wait = String(item.waiting_on || "");
  if (EXTERNAL_WAIT.has(wait)) return "calm";
  return "ok";
}

export function slaToneLabel(tone: SlaTone): string {
  switch (tone) {
    case "overdue":
      return "Просрочено";
    case "soon":
      return "Скоро";
    case "today":
      return "Сегодня";
    case "calm":
      return "Ждём снаружи";
    case "muted":
      return "Пауза / тест";
    default:
      return "В работе";
  }
}

/** Бейджи ситуации (не срочность). */
export function situationBadges(
  item: CaseIndicatorInput,
  opts?: { meUserId?: string | null },
): SituationBadge[] {
  const out: SituationBadge[] = [];
  const wait = String(item.waiting_on || "");
  const me = opts?.meUserId || null;

  if (item.is_test) {
    out.push({ id: "test", label: "Тест", kind: "test", title: "Тестовое дело" });
  }

  const needsReply =
    item.chat_awaits_staff === true ||
    (item.chat_awaits_staff !== false && wait === "staff");
  if (needsReply && !item.is_test) {
    out.push({
      id: "reply",
      label: "Нужен ответ",
      kind: "reply",
      title: "Ждёт ответа сотрудника (чат / waiting_on=staff)",
    });
  }

  if (wait === "client" || wait === "archive") {
    out.push({
      id: "docs",
      label: wait === "archive" ? "Архив" : "Ждём доки",
      kind: "docs",
      title: "Ожидаем документы от клиента или архив",
    });
  }
  if (wait === "payment" || item.finance_attention === "payable") {
    out.push({
      id: "pay",
      label: "Оплата",
      kind: "payment",
      title: "Ждём оплату — счета на вкладке Финансы",
    });
  } else if (item.finance_attention === "awaiting_invoice") {
    out.push({
      id: "need-invoice",
      label: "Нужен счёт",
      kind: "payment",
      title: "Счёт ещё не выставлен — откройте Финансы",
    });
  }
  if (wait === "sfr") {
    out.push({
      id: "sfr",
      label: "СФР",
      kind: "sfr",
      title: "Ждём ответ СФР",
    });
  }

  if (item.consent_accepted === false) {
    out.push({
      id: "noconsent",
      label: "Без согласия",
      kind: "consent",
      title: "Нет согласия на ПДн",
    });
  }

  if (item.max_linked) {
    out.push({ id: "max", label: "MAX", kind: "max", title: "MAX привязан" });
  }
  if (item.web_linked) {
    out.push({ id: "web", label: "сайт", kind: "web", title: "Веб-кабинет есть" });
  }

  if (me && item.expert_user_id === me) {
    out.push({ id: "mine", label: "Моё", kind: "mine", title: "Вы ответственный" });
  } else if (!item.expert_user_id) {
    out.push({
      id: "free",
      label: "Свободно",
      kind: "free",
      title: "Ответственный не назначен",
    });
  }

  const silent = Number(item.silent_days || 0);
  if (silent >= SILENT_THRESHOLD && !item.is_test) {
    out.push({
      id: "silent",
      label: `Тишина ${silent}д`,
      kind: "silent",
      title: `Нет контакта ${silent} дн.`,
    });
  }

  return out;
}

/** Последнее сообщение от клиента/представителя → ждём staff. */
export function chatAwaitsStaff(
  messages: Array<{ author_kind: string }> | null | undefined,
): boolean {
  if (!messages?.length) return false;
  const last = messages[messages.length - 1];
  const kind = String(last?.author_kind || "");
  return kind === "client" || kind === "representative";
}
