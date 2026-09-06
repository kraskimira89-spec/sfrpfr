/** Имя вида «MAX 12345» — заглушка, не ФИО. */
export function isMaxPlaceholderName(name: string | null | undefined): boolean {
  const raw = (name || "").trim();
  if (!raw) return true;
  return /^MAX\s+\d+$/i.test(raw);
}

export function displayClientFio(name: string | null | undefined): string | null {
  const raw = (name || "").trim();
  if (!raw || isMaxPlaceholderName(raw)) return null;
  return raw;
}

/** Имя из приветствия бота: «Здравствуйте, Владимир!» */
const GREETING_RE = /^Здравствуйте,\s+([A-ZА-ЯЁ][A-Za-zА-Яа-яЁё-]{1,39})!/u;

export function greetingNameFromBotMessages(
  messages: { author_kind: string; body: string }[],
): string | null {
  for (const message of messages) {
    if (message.author_kind !== "system") continue;
    const match = (message.body || "").match(GREETING_RE);
    const name = match?.[1]?.trim();
    if (name && !/^MAX$/i.test(name)) return name;
  }
  return null;
}

export function clientNameForChatHeader(
  storedName: string | null | undefined,
  messages: { author_kind: string; body: string }[],
): string | null {
  return displayClientFio(storedName) ?? greetingNameFromBotMessages(messages);
}
