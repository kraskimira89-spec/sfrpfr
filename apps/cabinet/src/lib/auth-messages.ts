/** Клиентские тексты входа. Технические детали (Supabase, JWT, HTTP) сюда не попадают. */

export const AUTH_ERROR_CODES = [
  "AUTH_INVALID_EMAIL",
  "AUTH_RATE_LIMITED",
  "AUTH_CODE_INVALID",
  "AUTH_CODE_EXPIRED",
  "AUTH_DELIVERY_FAILED",
  "AUTH_PROVIDER_UNAVAILABLE",
  "AUTH_CONFIG_MISSING",
  "AUTH_UNKNOWN",
] as const;

export type AuthErrorCode = (typeof AUTH_ERROR_CODES)[number];

export const AUTH_MESSAGES: Record<AuthErrorCode, string> = {
  AUTH_INVALID_EMAIL: "Проверьте адрес почты: например, name@example.ru.",
  AUTH_RATE_LIMITED: "Вы недавно запрашивали код. Попробуйте ещё раз через 60 секунд.",
  AUTH_CODE_INVALID: "Код не подошёл. Проверьте цифры или запросите новый.",
  AUTH_CODE_EXPIRED: "Срок действия кода закончился. Запросите новый код.",
  AUTH_DELIVERY_FAILED:
    "Сейчас не удаётся отправить код. Попробуйте позже или войдите через MAX.",
  AUTH_PROVIDER_UNAVAILABLE:
    "Сейчас не удаётся отправить код. Попробуйте позже или войдите через MAX.",
  AUTH_CONFIG_MISSING: "Вход временно недоступен. Попробуйте позже или напишите нам в MAX.",
  AUTH_UNKNOWN: "Сейчас не удаётся войти. Попробуйте позже или напишите нам в MAX.",
};

export const AUTH_COPY = {
  title: "Войти в личный кабинет",
  subtitle:
    "Введите почту, которую вы указали при обращении. Мы отправим одноразовый код — пароль придумывать не нужно.",
  emailLabel: "Электронная почта",
  emailRequired: "Введите адрес электронной почты.",
  getCode: "Получить код",
  otpSentGeneric:
    "Если этот адрес можно использовать для входа, мы отправили код на почту. Проверьте входящие письма и папку «Спам».",
  otpResent: "Код отправлен повторно. Проверьте почту и папку «Спам».",
  checkInboxTitle: "Проверьте почту",
  checkInboxLead: "Мы отправили код на",
  enterCode: "Введите код из письма.",
  usuallyFast: "Обычно письмо приходит быстро. Если его нет, проверьте папку «Спам».",
  noInstantPromise: "Не пришёл код? Подождите немного, затем проверьте папки «Спам» и «Рассылки».",
  changeEmail: "Изменить почту",
  signIn: "Войти",
  maxHint: "Уже общались с нами в MAX? Войдите через тот же чат по делу.",
  maxCta: "Войти через MAX",
  maxWaiting: "Подтвердите вход в MAX. Мы ждём подтверждение здесь. Не закрывайте эту страницу.",
  maxTitle: "Войти через MAX",
  maxLead:
    "Откроется бот MAX. Подтвердите вход в сообщении, затем вернитесь в кабинет — вход выполнится автоматически.",
  maxContinue: "Продолжить в MAX",
  helpTitle: "Нет доступа к почте или не получается войти?",
  helpMax: "Написать в MAX",
  helpSite: "Оставить заявку на сайте",
  configMissing: AUTH_MESSAGES.AUTH_CONFIG_MISSING,
  passwordLink: "Войти по паролю",
  emailFallback: "Выбрать вход по почте",
  cancel: "Отменить",
  trustTitle: "Безопасный вход",
  trustItems: [
    "Пароль не нужен",
    "Код действует ограниченное время",
    "Документы доступны только после входа",
  ],
} as const;

const TECHNICAL_LEAK =
  /supabase|jwt|oauth|database|stack|public ключ|public key|anon[_ ]key|service[_ ]role|\b500\b|\b401\b|\b403\b|\b404\b|\b503\b|internal|postgres|fetch failed|econnrefused|enotfound|unexpected_failure/i;

export function isTechnicalAuthLeak(text: string): boolean {
  return TECHNICAL_LEAK.test(text);
}

export function isValidEmailAddress(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

export function maskEmail(email: string): string {
  const trimmed = email.trim();
  const at = trimmed.indexOf("@");
  if (at <= 0) return "вашу почту";
  const local = trimmed.slice(0, at);
  const domain = trimmed.slice(at + 1);
  const visible = local.slice(0, 1);
  return `${visible}***@${domain}`;
}

export function safeAuthNotice(text: string, fallback: AuthErrorCode = "AUTH_UNKNOWN"): string {
  const t = String(text || "").trim();
  if (!t || isTechnicalAuthLeak(t) || t.length > 180) {
    return AUTH_MESSAGES[fallback];
  }
  return t;
}

export function mapAuthError(error: unknown, fallback: AuthErrorCode = "AUTH_UNKNOWN"): string {
  const raw =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  const lower = raw.toLowerCase();
  if (/rate.?limit|too many|over_email|429/.test(lower)) {
    return AUTH_MESSAGES.AUTH_RATE_LIMITED;
  }
  if (/expired|otp_expired|token has expired/.test(lower)) {
    return AUTH_MESSAGES.AUTH_CODE_EXPIRED;
  }
  if (/invalid.?email|email_address_invalid|unable to validate email/.test(lower)) {
    return AUTH_MESSAGES.AUTH_INVALID_EMAIL;
  }
  if (fallback === "AUTH_CODE_INVALID") {
    return AUTH_MESSAGES.AUTH_CODE_INVALID;
  }
  if (isTechnicalAuthLeak(raw) || raw.length > 180 || !raw) {
    return AUTH_MESSAGES[fallback];
  }
  return AUTH_MESSAGES[fallback];
}

export function logAuthDiagnostic(code: AuthErrorCode, detail?: string): void {
  if (process.env.NODE_ENV !== "development") return;
  console.warn(`[auth] ${code}`, detail ?? "");
}
