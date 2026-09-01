export const BOT_TYPING_MS = 3_000;

/** Подсказка «дольше обычного», пока бот ещё может ответить. */
export const BOT_TYPING_SLOW_MS = 25_000;

/** После этого срока UI скрывает индикатор; backend помечает job failed + handoff. */
export const BOT_TYPING_TIMEOUT_MS = 55_000;

export const BOT_TYPING_PROCESSING_HINT = "Сообщение отправлено. Готовим ответ…";

export const BOT_TYPING_SLOW_HINT =
  "Ответ занимает больше времени, чем обычно. Ваш вопрос сохранён. Можно подождать или написать специалисту.";

export const BOT_TYPING_TIMEOUT_HINT =
  "Сейчас бот не смог подготовить ответ. Ваше сообщение сохранено и передано специалисту. Мы ответим в этом же чате.";

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
  if (!Number.isNaN(t) && Number.isFinite(t)) {
    return Math.max(0, nowMs - t);
  }
  return 0;
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

export function botTypingHint(ageMs: number | null): string | null {
  if (ageMs === null) return null;
  if (ageMs < BOT_TYPING_MS) return BOT_TYPING_PROCESSING_HINT;
  if (ageMs < BOT_TYPING_SLOW_MS) return BOT_TYPING_PROCESSING_HINT;
  if (ageMs < BOT_TYPING_TIMEOUT_MS) return BOT_TYPING_SLOW_HINT;
  return null;
}
