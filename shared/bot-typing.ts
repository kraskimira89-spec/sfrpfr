export const BOT_TYPING_MS = 8_000;

/** После этого срока индикатор и подсказка скрываются, даже если бот так и не ответил. */
export const BOT_TYPING_TIMEOUT_MS = 50_000;

export const BOT_TYPING_TIMEOUT_HINT =
  "Ответ задерживается. Подождите минуту или напишите ещё раз — сообщение уже в чате по делу.";

export type BotTypingMessage = {
  id?: string;
  author_kind: string;
  created_at?: string;
  body?: string;
};

function isClientAuthor(kind: string): boolean {
  return kind === "client" || kind === "representative";
}

function isDocumentEvent(body?: string): boolean {
  return String(body || "").startsWith("[Документ]");
}

export function lastClientAwaitAgeMs(
  messages: BotTypingMessage[],
  nowMs: number = Date.now(),
): number | null {
  const last = messages[messages.length - 1];
  if (!last || !isClientAuthor(last.author_kind) || isDocumentEvent(last.body)) {
    return null;
  }
  const t = Date.parse(String(last.created_at || ""));
  if (!Number.isFinite(t)) return 0;
  return Math.max(0, nowMs - t);
}

export function isAwaitingBotReply(
  messages: BotTypingMessage[],
  nowMs: number = Date.now(),
): boolean {
  const age = lastClientAwaitAgeMs(messages, nowMs);
  return age !== null && age < BOT_TYPING_TIMEOUT_MS;
}

/** Ключ последнего клиентского сообщения — таймер сбрасывается только при смене ключа. */
export function awaitingBotReplyKey(messages: BotTypingMessage[]): string | null {
  const last = messages[messages.length - 1];
  if (!last || !isClientAuthor(last.author_kind) || isDocumentEvent(last.body)) {
    return null;
  }
  return last.id ?? `${last.created_at ?? ""}:${last.author_kind}`;
}
