export type ChatMessageLike = {
  id?: string;
  author_kind?: string;
  body?: string;
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

/** Системные события ленты, после которых подсказки тоже устаревают. */
function isSuggestTriggerSystem(body: string | undefined): boolean {
  const text = (body || "").trim();
  return (
    text.startsWith("[Документ]") ||
    text.includes("подтвердил тип документа") ||
    text.includes("указал тип документа")
  );
}

/**
 * Id последнего события, после которого подсказки надо перегенерировать:
 * сообщение клиента, присланный документ или подтверждение типа документа.
 * Раньше триггером был только текст клиента — после файла/подтверждения
 * подсказки оставались старыми.
 */
export function latestSuggestionTriggerId(messages: ChatMessageLike[]): string | null {
  let id: string | null = null;
  for (const message of messages || []) {
    if (!message || !message.id) continue;
    if (message.author_kind === "client") {
      id = message.id;
    } else if (message.author_kind === "system" && isSuggestTriggerSystem(message.body)) {
      id = message.id;
    }
  }
  return id;
}
