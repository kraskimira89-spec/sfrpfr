/** Разбор ФИО для шапки чата (зеркало Python sfrfr.utils.person_name). */

const PATRONYMIC_RE =
  /^(?:.*(ович|евич|ич|овна|евна|ична|инична)|.*(ovich|evich|ovna|evna|ich))$/iu;

const TOKEN_RE =
  /^[A-Za-zА-Яа-яЁёІіЇїЄєҐґ](?:[A-Za-zА-Яа-яЁёІіЇїЄєҐґ'`’\-]*[A-Za-zА-Яа-яЁёІіЇїЄєҐґ])?$/u;

const VOWELS = new Set(
  "аеёиоуыэюяaeiouyіїєґАЕЁИОУЫЭЮЯAEIOUYІЇЄҐ".split(""),
);

const PLACEHOLDER_RE =
  /^(max(\s+user)?\s*\d*|клиент|client|user|guest|test|тест|аноним)$/iu;

function isPlaceholderName(name: string | null | undefined): boolean {
  const raw = (name || "").trim();
  if (!raw) return true;
  if (raw.includes("@")) return true;
  if (PLACEHOLDER_RE.test(raw)) return true;
  if (/^max\s+\d+/i.test(raw)) return true;
  return false;
}

/** Имя вида «MAX 12345» — заглушка, не ФИО. */
export function isMaxPlaceholderName(name: string | null | undefined): boolean {
  return isPlaceholderName(name);
}

function looksLikeToken(token: string): boolean {
  const t = token.trim();
  if (t.length < 2 || t.length > 40) return false;
  if (!TOKEN_RE.test(t)) return false;
  if (/\d/.test(t)) return false;
  if (/(.)\1{3,}/u.test(t)) return false;
  const letters = [...t].filter((c) => /\p{L}/u.test(c));
  if (letters.length < 2) return false;
  const vowels = letters.filter((c) => VOWELS.has(c)).length;
  if (letters.length >= 4 && vowels === 0) return false;
  if (letters.length >= 6 && vowels / letters.length < 0.15) return false;
  const hasCyr = letters.some((c) => /[А-Яа-яЁёІіЇїЄєҐґ]/u.test(c));
  const hasLat = letters.some((c) => /[A-Za-z]/.test(c));
  if (hasCyr && hasLat) return false;
  return true;
}

function looksLikePatronymic(token: string): boolean {
  return looksLikeToken(token) && PATRONYMIC_RE.test(token);
}

function titleCaseToken(token: string): string {
  return token
    .split(/([-'`’])/u)
    .map((part) => {
      if (!part || /[-'`’]/u.test(part)) return part;
      return part[0].toUpperCase() + part.slice(1).toLowerCase();
    })
    .join("");
}

function isCyrillicWord(token: string): boolean {
  return /[А-Яа-яЁёІіЇїЄєҐґ]/u.test(token);
}

function cleanTokens(fullName: string): string[] {
  const raw = fullName.replace(/,/g, " ").trim().replace(/\s+/g, " ");
  if (!raw || isPlaceholderName(raw)) return [];
  const tokens = raw.split(/\s+/).filter(Boolean);
  const good = tokens.filter(looksLikeToken).map(titleCaseToken);
  if (tokens.length && good.length < Math.max(1, Math.ceil(tokens.length / 2))) {
    return [];
  }
  return good;
}

export type ParsedClientName = {
  display: string | null;
  salutation: string;
  needsConfirm: boolean;
};

export function parseClientName(fullName: string | null | undefined): ParsedClientName {
  const raw = (fullName || "").trim().replace(/\s+/g, " ");
  if (!raw || isPlaceholderName(raw)) {
    return { display: null, salutation: "Клиент", needsConfirm: true };
  }
  const tokens = cleanTokens(raw);
  if (!tokens.length) {
    return { display: null, salutation: "Клиент", needsConfirm: true };
  }

  let surname: string | null = null;
  let given: string | null = null;
  let patronymic: string | null = null;
  let confidence: "high" | "medium" | "low" = "medium";

  if (tokens.length >= 3 && looksLikePatronymic(tokens[2])) {
    surname = tokens[0];
    given = tokens[1];
    patronymic = tokens[2];
    confidence = tokens.length > 3 ? "medium" : "high";
  } else if (tokens.length === 2 && looksLikePatronymic(tokens[1])) {
    given = tokens[0];
    patronymic = tokens[1];
    confidence = "high";
  } else if (tokens.length === 2) {
    const [a, b] = tokens;
    if (isCyrillicWord(a) || isCyrillicWord(b)) {
      surname = a;
      given = b;
    } else {
      given = a;
      surname = b;
    }
  } else if (tokens.length === 1) {
    given = tokens[0];
  } else {
    surname = tokens[0];
    given = tokens[1];
    if (looksLikePatronymic(tokens[2])) {
      patronymic = tokens[2];
      confidence = "high";
    } else {
      confidence = "low";
    }
  }

  if (confidence === "low" || !given) {
    return { display: null, salutation: "Клиент", needsConfirm: true };
  }

  const salutation = patronymic ? `${given} ${patronymic}` : given;
  let displayParts = [surname, given, patronymic].filter(Boolean) as string[];
  if (
    surname &&
    given &&
    !patronymic &&
    !isCyrillicWord(surname) &&
    !isCyrillicWord(given)
  ) {
    displayParts = [given, surname];
  }
  return {
    display: displayParts.join(" ") || null,
    salutation,
    needsConfirm: confidence !== "high",
  };
}

export function displayClientFio(name: string | null | undefined): string | null {
  return parseClientName(name).display;
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
    if (name && parseClientName(name).display) return name;
  }
  return null;
}

export function clientNameForChatHeader(
  storedName: string | null | undefined,
  messages: { author_kind: string; body: string }[],
): string | null {
  return displayClientFio(storedName) ?? greetingNameFromBotMessages(messages);
}

export function clientNameNeedsConfirm(
  storedName: string | null | undefined,
): boolean {
  return parseClientName(storedName).needsConfirm;
}
