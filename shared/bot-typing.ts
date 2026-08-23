export const BOT_TYPING_TIMEOUT_MS = 50_000;

export const BOT_TYPING_TIMEOUT_HINT =
  "Бот не ответил. Напишите ещё раз или откройте чат MAX";

export type BotTypingMessage = {
  id?: string;
  author_kind: string;
  created_at?: string;
};

export function isAwaitingBotReply(messages: BotTypingMessage[]): boolean {
  const last = messages[messages.length - 1];
  if (!last) return false;
  return last.author_kind === "client" || last.author_kind === "representative";
}

/** Ключ последнего клиентского сообщения — таймер сбрасывается только при смене ключа. */
export function awaitingBotReplyKey(messages: BotTypingMessage[]): string | null {
  const last = messages[messages.length - 1];
  if (!last) return null;
  if (last.author_kind !== "client" && last.author_kind !== "representative") return null;
  return last.id ?? `${last.created_at ?? ""}:${last.author_kind}`;
}
