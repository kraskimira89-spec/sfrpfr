export type ChatMessageLike = {
  id?: string;
  author_kind?: string;
};

/** Убрать отправленный черновик из списка подсказок. */
export function withoutSentSuggestion(suggestions: string[], sent: string): string[] {
  const needle = (sent || "").trim();
  if (!needle) return suggestions.slice();
  return suggestions.filter((item) => item.trim() !== needle);
}

/** Id последнего сообщения клиента — чтобы перегенерировать подсказки. */
export function latestClientMessageId(messages: ChatMessageLike[]): string | null {
  let id: string | null = null;
  for (const message of messages || []) {
    if (message && message.author_kind === "client" && message.id) {
      id = message.id;
    }
  }
  return id;
}
