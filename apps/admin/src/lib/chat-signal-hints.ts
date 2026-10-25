/**
 * Косвенные признаки из текста клиента → подсказки сотруднику.
 * Не подтверждают оплату / передачу / подачу.
 */

export type ChatSignalKind = "payment_claim" | "docs_sent_claim" | "submission_claim";

export type ChatSignalHint = {
  kind: ChatSignalKind;
  label: string;
  staffAction: string;
};

const RULES: { kind: ChatSignalKind; re: RegExp; label: string; staffAction: string }[] = [
  {
    kind: "payment_claim",
    re: /оплатил|оплатила|оплатили|деньги\s+ушли|перев[её]л|перевела|квитанци/i,
    label: "Клиент сообщил об оплате — проверить",
    staffAction: "Сверить заказ в Финансах / ЮKassa; не ставить paid по тексту чата",
  },
  {
    kind: "docs_sent_claim",
    re: /отправил\s+документ|отправила\s+документ|выслал|выслала|прикрепил|загрузил\s+файл|скинул\s+файл/i,
    label: "Клиент сообщил об отправке документов — проверить загрузку",
    staffAction: "Проверить таблицу документов и доставку; не считать пакет переданным",
  },
  {
    kind: "submission_claim",
    re: /подал\s+через|подала\s+через|отправил\s+в\s+сфр|на\s+госуслуг|через\s+госуслуг/i,
    label: "Клиент заявил о подаче — подтвердить отдельно",
    staffAction: "Зафиксировать подачу только с датой/адресатом после проверки источника",
  },
];

export function detectChatSignalHints(
  messages: { author_kind?: string; text?: string | null; body?: string | null }[],
  limit = 5,
): ChatSignalHint[] {
  const out: ChatSignalHint[] = [];
  const seen = new Set<ChatSignalKind>();
  for (let i = messages.length - 1; i >= 0 && out.length < limit; i -= 1) {
    const m = messages[i];
    if (String(m.author_kind || "").toLowerCase() !== "client") continue;
    const text = String(m.text || m.body || "");
    if (!text.trim()) continue;
    for (const rule of RULES) {
      if (seen.has(rule.kind)) continue;
      if (rule.re.test(text)) {
        seen.add(rule.kind);
        out.push({
          kind: rule.kind,
          label: rule.label,
          staffAction: rule.staffAction,
        });
      }
    }
  }
  return out;
}
