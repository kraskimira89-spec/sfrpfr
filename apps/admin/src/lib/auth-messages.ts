/** Тексты входа сотрудника. Без Supabase, staff_roles, JWT и перечисления аккаунтов. */

export const STAFF_AUTH_MESSAGES = {
  AUTH_INVALID_EMAIL: "Проверьте адрес почты: например, name@company.ru.",
  AUTH_RATE_LIMITED: "Вы недавно запрашивали код. Попробуйте ещё раз через 60 секунд.",
  AUTH_CODE_INVALID: "Код не подошёл. Проверьте цифры или запросите новый.",
  AUTH_CODE_EXPIRED: "Срок действия кода закончился. Запросите новый.",
  AUTH_CODE_REQUIRED: "Введите код из письма.",
  AUTH_DELIVERY_FAILED:
    "Сейчас не удаётся отправить код. Попробуйте позже или войдите через MAX.",
  AUTH_EMAIL_UNKNOWN:
    "Этот адрес не зарегистрирован для входа. Обратитесь к администратору — мы отправили запрос на proverkastaza@yandex.ru.",
  AUTH_CONFIG_MISSING:
    "Вход временно недоступен. Попробуйте позже или используйте согласованный рабочий способ связи.",
  AUTH_UNKNOWN: "Сейчас не удаётся войти. Попробуйте позже или войдите через MAX.",
} as const;

export const STAFF_LOGIN_COPY = {
  title: "Вход в кабинет сотрудника",
  subtitle:
    "Введите рабочую почту. Мы отправим одноразовый код для входа. Пароль придумывать не нужно.",
  emailLabel: "Рабочая почта",
  emailPlaceholder: "name@company.ru",
  emailRequired: "Введите рабочую почту.",
  getCode: "Получить код",
  otpSentGeneric: "Код отправлен на рабочую почту. Проверьте входящие и папку «Спам».",
  otpResent: "Новый код отправлен. Проверьте рабочую почту и папку «Спам».",
  checkInboxTitle: "Проверьте рабочую почту",
  checkInboxLead: "Мы отправили одноразовый код на:",
  enterCode: "Введите код из письма. Код действует ограниченное время.",
  changeEmail: "Изменить почту",
  signIn: "Войти",
  orDivider: "или",
  maxTeaserTitle: "Уже работаете через MAX?",
  maxTeaserLead:
    "Подтвердите вход в Ops-боте MAX. Используйте этот способ, если ваш MAX уже привязан к рабочему профилю.",
  maxCta: "Войти через MAX",
  maxTitle: "Подтвердите вход в MAX",
  maxLead:
    "Откроется Ops-бот MAX. Подтвердите вход в сообщении. После подтверждения кабинет откроется автоматически.",
  maxOpen: "Открыть Ops-бот MAX",
  maxWaiting: "Ожидаем подтверждение в MAX…",
  maxCancel: "Отменить вход через MAX",
  maxEmailFallback: "Войти по рабочей почте",
  accessRequestLink: "Нет доступа к кабинету? Запросить доступ",
  backToSite: "← Вернуться на основной сайт",
  registerTitle: "Запросить доступ сотрудника",
  registerLead:
    "Заполните заявку с рабочими данными. Администратор проверит запрос и назначит роль, если доступ согласован.",
  registerSubmit: "Отправить запрос доступа",
  registerDone:
    "Запрос отправлен. Доступ не открывается автоматически. После решения администратора мы сообщим на рабочую почту или в MAX, если он привязан к вашему профилю.",
  registerPending:
    "Ваш запрос доступа находится на рассмотрении. Мы сообщим, когда администратор примет решение.",
  backToLogin: "← Вернуться ко входу",
  accessPendingTitle: "Доступ пока не подтверждён",
  accessPendingLead:
    "Вход выполнен, но доступ к кабинету ещё не назначен. Отправьте запрос доступа или обратитесь к администратору.",
  accessRequestCta: "Запросить доступ",
  accessBlockedTitle: "Доступ временно ограничен",
  accessBlockedLead:
    "Доступ к кабинету временно ограничен. Обратитесь к администратору через согласованный рабочий канал.",
  signOut: "Выйти",
  trustTitle: "Безопасный вход",
  trustItems: [
    "Пароль не нужен — используется одноразовый код",
    "Доступ к данным клиентов получают только сотрудники с назначенной ролью",
    "Вход и действия в кабинете фиксируются для защиты данных",
  ],
} as const;

const TECHNICAL_LEAK =
  /supabase|jwt|staff[_ -]?roles?|staff-grant|rbac|rls|oauth|database|stack|public ключ|public key|anon[_ ]key|service[_ ]role|\b500\b|\b401\b|\b403\b|\b404\b|\b503\b|internal|postgres|fetch failed|econnrefused|enotfound|unexpected_failure|signups not allowed|user not found/i;

export function isTechnicalStaffAuthLeak(text: string): boolean {
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
  if (local.length <= 2) return `${local[0] ?? "*"}***@${domain}`;
  return `${local[0]}${"*".repeat(Math.max(1, local.length - 2))}${local.slice(-1)}@${domain}`;
}

export function mapStaffAuthError(
  error: unknown,
  fallback: string = STAFF_AUTH_MESSAGES.AUTH_UNKNOWN,
): string {
  const raw =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  const lower = raw.toLowerCase();
  if (/rate.?limit|too many|over_email|429/.test(lower)) {
    return STAFF_AUTH_MESSAGES.AUTH_RATE_LIMITED;
  }
  if (/expired|otp_expired|token has expired/.test(lower)) {
    return STAFF_AUTH_MESSAGES.AUTH_CODE_EXPIRED;
  }
  if (/invalid.?email|email_address_invalid|unable to validate email/.test(lower)) {
    return STAFF_AUTH_MESSAGES.AUTH_INVALID_EMAIL;
  }
  if (/invalid|otp|token|code/.test(lower)) {
    return STAFF_AUTH_MESSAGES.AUTH_CODE_INVALID;
  }
  if (isTechnicalStaffAuthLeak(raw) || raw.length > 180 || !raw) {
    return fallback;
  }
  return fallback;
}

export function safeStaffAuthNotice(text: string, fallback = STAFF_AUTH_MESSAGES.AUTH_UNKNOWN): string {
  const t = String(text || "").trim();
  if (!t || isTechnicalStaffAuthLeak(t) || t.length > 180) {
    return fallback;
  }
  return t;
}
