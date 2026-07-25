"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type CaseSummary = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  expert_assigned: boolean;
  checklist_open_count: number;
  next_action: string | null;
  unread_messages: number;
  consent_accepted: boolean;
};

type ChecklistItem = {
  id: string;
  title: string;
  item_type: string;
  owner: string;
  status: string;
  note?: string | null;
  due_at?: string | null;
};

type CaseDocument = {
  id: string;
  storage_path: string;
  doc_type?: string | null;
  created_at?: string;
};

type CaseDetail = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  expert_assigned: boolean;
  consent_accepted: boolean;
  checklist_items: ChecklistItem[];
  required_documents: ChecklistItem[];
  documents: CaseDocument[];
  findings?: { type: string; detail: string; severity?: string }[];
  draft: { title?: string; body?: string; needs_human_review?: boolean } | null;
  next_action?: string | null;
  status_label?: string | null;
  status_hint?: string | null;
  pipeline_error?: string | null;
  submission_instruction: string;
  warning: string;
};

type CaseMessage = {
  id: string;
  author_kind: string;
  body: string;
  created_at: string;
};

type ConsentBundle = {
  consents: { id: string; version: string; accepted_at: string }[];
  contract_acceptances: { id: string; offer_version: string; accepted_at: string }[];
  offer_url: string;
  pdn_url: string;
  consent_url: string;
};

type OrderRow = {
  id: string;
  package_code: string;
  amount_rub: number | string;
  status: string;
  created_at?: string;
  payments?: { id: string; status: string; paid_at?: string | null }[];
};

type ResultPayload = {
  evidence: {
    monthly_before_rub?: number | null;
    monthly_after_rub?: number | null;
    lump_sum_rub?: number | null;
    confirmed_at?: string | null;
    document_id?: string | null;
  } | null;
  success_fee: {
    sf_lump: number;
    sf_month: number;
    sf_total: number;
    lump_sum_rub: number;
    monthly_increase_rub: number;
  };
  post_payment_note: string;
  warning: string;
};

type PreferredChannel = "max_miniapp" | "web_cabinet" | "unset";

type PortalMe = {
  user_id: string;
  email?: string | null;
  client_id?: string | null;
  preferred_channel: PreferredChannel;
  max_linked: boolean;
  web_linked: boolean;
  max_user_id?: string | null;
  cabinet_url: string;
  max_bot_url: string;
  max_miniapp_url: string;
};

type View = "cases" | "case" | "docs" | "payments" | "result";
/** phone — только в архиве, пока AUTH_SMS_PUBLISHED = false */
type AuthChannel = "email" | "phone" | "max";
type AuthScreen = "login" | "register" | "recover" | "max" | "email_otp";
type RegisterChannel = "email" | "max";
type LoginMethod = "password" | "max" | "email_otp";

/** SMS-вход не публикуем (см. apps/cabinet/src/archive/auth-sms.md). */
const AUTH_SMS_PUBLISHED = false;
const MIN_PASSWORD_LEN = 8;

function hasPasswordSet(session: Session | null): boolean {
  if (!session?.user) return false;
  const meta = session.user.user_metadata as Record<string, unknown> | undefined;
  return meta?.password_set === true;
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
const SITE_URL = "https://taxi-doroga-dobra.ru";
const CABINET_PUBLIC_URL =
  process.env.NEXT_PUBLIC_CABINET_PUBLIC_URL ?? "https://cabinet.taxi-doroga-dobra.ru";
const DEFAULT_MAX_CHAT = "https://max.ru/id8905998693_1_bot";
const DEFAULT_MAX_MINIAPP = "https://max.ru/id8905998693_1_bot?startapp";
const MAX_BOT_HANDLE = "@id8905998693_1_bot";

/** Единые термины: чат MAX / браузер / страница входа / почта (как в боте). */
const AUTH_COPY = {
  chatMax: "чат MAX",
  browser: "браузер",
  loginPage: "страница входа",
  email: "почта",
  showCodeBtn: "Показать код для MAX",
  confirmBtn: "Подтвердить вход в браузере",
  openedChatBtn: "Я открыл чат MAX",
  pressedStartBtn: "Я нажал «Начать» — продолжить на странице входа",
} as const;

/** Ссылка на диалог с ботом (без ?startapp — иначе веб показывает «Запустить бота»). */
function chatUrlOnly(url: string): string {
  try {
    const u = new URL(url || DEFAULT_MAX_CHAT);
    u.searchParams.delete("startapp");
    return u.toString().replace(/\?$/, "");
  } catch {
    return DEFAULT_MAX_CHAT;
  }
}

const PACKAGE_LABELS: Record<string, string> = {
  DIAG: "Диагностика",
  ACCOMP: "Сопровождение",
  SF_LUMP: "Post-payment (ЕДВ)",
  SF_MONTH: "Post-payment (ежемесячная прибавка)",
};

const STATUS_LABELS: Record<string, string> = {
  intake: "Приём",
  documents_received: "Документы получены",
  ocr_done: "OCR",
  classified: "Классификация",
  extracted: "Извлечение",
  audited: "Аудит",
  draft_ready: "Черновик готов",
  human_review: "Проверка эксперта",
  completed: "Завершено",
  failed: "Ошибка",
  lead: "Заявка",
  consent_accepted: "Согласие принято",
  diagnostic_paid: "Диагностика оплачена",
  contract_accepted: "Заказ принят",
  service_paid: "Сопровождение оплачено",
  package_delivered: "Пакет выдан",
  awaiting_client_submission: "Ожидаем вашу подачу",
  result_pending: "Ждём решение СФР",
  result_confirmed: "Результат подтверждён",
  success_fee_due: "Счёт за результат",
  success_fee_paid: "Вознаграждение оплачено",
  closed: "Закрыто",
};

function labelStatus(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function shortId(id: string) {
  return id.slice(0, 8);
}

async function apiFetch<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function ClientCabinet() {
  const supabase = useMemo(
    () =>
      supabaseUrl && supabaseKey
        ? createClient(supabaseUrl, supabaseKey, {
            auth: {
              detectSessionInUrl: true,
              persistSession: true,
              flowType: "pkce",
            },
          })
        : null,
    [],
  );
  const [session, setSession] = useState<Session | null>(null);
  const [authScreen, setAuthScreen] = useState<AuthScreen>("register");
  const [loginMethod, setLoginMethod] = useState<LoginMethod>("password");
  const [registerChannel, setRegisterChannel] = useState<RegisterChannel>("max");
  const [authChannel, setAuthChannel] = useState<AuthChannel>("max");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [maxTicket, setMaxTicket] = useState("");
  const [maxPairCode, setMaxPairCode] = useState("");
  const [maxWaitStatus, setMaxWaitStatus] = useState("");
  const [maxBotUrl, setMaxBotUrl] = useState(DEFAULT_MAX_CHAT);
  const [maxLinkBusy, setMaxLinkBusy] = useState(false);
  const [maxWizardStep, setMaxWizardStep] = useState<1 | 2 | 3>(1);
  const [maxStep1Done, setMaxStep1Done] = useState(false);
  const [maxStep2Done, setMaxStep2Done] = useState(false);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [notice, setNotice] = useState("");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [casesReady, setCasesReady] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [messages, setMessages] = useState<CaseMessage[]>([]);
  const [messageBody, setMessageBody] = useState("");
  const [consents, setConsents] = useState<ConsentBundle | null>(null);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [result, setResult] = useState<ResultPayload | null>(null);
  const [view, setView] = useState<View>("cases");
  const [busy, setBusy] = useState(false);
  const [payingOrderId, setPayingOrderId] = useState<string | null>(null);
  const [me, setMe] = useState<PortalMe | null>(null);
  const ensureCaseRef = useRef(false);

  const token = session?.access_token;

  // Query: ?mode=register|recover|login; ?channel=max; ?register=max
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mode = (params.get("mode") || "").toLowerCase();
    const channel = (params.get("channel") || "").toLowerCase();
    const registerMax =
      params.get("register")?.toLowerCase() === "max" || channel === "max";
    const t = window.setTimeout(() => {
      if (mode === "recover") {
        setAuthScreen("recover");
        return;
      }
      if (mode === "login") {
        setAuthScreen("login");
        if (registerMax) {
          setLoginMethod("max");
          setAuthChannel("max");
        } else {
          setLoginMethod("password");
          setAuthChannel("email");
        }
        return;
      }
      // register (явный) или дефолт новичка через MAX
      if (mode === "register" || registerMax || !mode) {
        setAuthScreen("register");
        if (registerMax || !mode) {
          setRegisterChannel("max");
          setAuthChannel("max");
          setMaxWizardStep(1);
        }
      }
    }, 0);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
    });
    const { data } = supabase.auth.onAuthStateChange((event, nextSession) => {
      setSession(nextSession);
      if (event === "PASSWORD_RECOVERY") {
        setRecoveryMode(true);
        setAuthScreen("recover");
      } else if (!nextSession) {
        setRecoveryMode(false);
      }
    });
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  // Одноразовая ссылка из MAX: /?auth=max&t=...
  useEffect(() => {
    if (!supabase || !apiBase || session || maxLinkBusy) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("auth") !== "max") return;
    const linkToken = params.get("t");
    if (!linkToken) return;

    let cancelled = false;
    // Состояние UI — после тика, чтобы не триггерить set-state-in-effect
    const kickoff = window.setTimeout(() => {
      if (cancelled) return;
      setMaxLinkBusy(true);
      setBusy(true);
      setNotice("Подтверждаем вход из чата MAX…");
    }, 0);

    void (async () => {
      try {
        const response = await fetch(`${apiBase}/api/portal/auth/otp/link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ t: linkToken }),
        });
        const body = (await response.json().catch(() => ({}))) as {
          detail?: string;
          token_hash?: string;
          type?: "email" | "sms";
        };
        if (!response.ok) {
          throw new Error(
            typeof body.detail === "string"
              ? body.detail
              : `Ссылка недействительна или устарела. Запросите вход снова в ${AUTH_COPY.chatMax}.`,
          );
        }
        const { error } = await supabase.auth.verifyOtp({
          token_hash: body.token_hash || "",
          type: body.type || "email",
        });
        if (error) throw error;
        if (!cancelled) {
          params.delete("auth");
          params.delete("t");
          const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
          window.history.replaceState({}, "", next);
          setNotice("");
        }
      } catch (err) {
        if (!cancelled) {
          setNotice(
            err instanceof Error
              ? err.message
              : "Не удалось войти по ссылке из чата MAX.",
          );
        }
      } finally {
        if (!cancelled) {
          setBusy(false);
          setMaxLinkBusy(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      window.clearTimeout(kickoff);
    };
  }, [supabase, session, maxLinkBusy]);

  const loadCases = useCallback(async () => {
    if (!token || !apiBase) return;
    try {
      const rows = await apiFetch<CaseSummary[]>("/api/portal/me/cases", token);
      setCases(rows);
      setCasesReady(true);
      setNotice("");
    } catch {
      setCasesReady(true);
      setNotice("Не удалось загрузить дела. Повторите попытку позже.");
    }
  }, [token]);

  const loadMe = useCallback(async () => {
    if (!token || !apiBase) return;
    try {
      const profile = await apiFetch<PortalMe>("/api/portal/me", token);
      setMe(profile);
      const params = new URLSearchParams(window.location.search);
      const linkMax = params.get("link_max");
      const linkToken = params.get("link_token");
      if ((linkMax || linkToken) && !profile.max_linked) {
        const linked = await apiFetch<PortalMe>("/api/portal/link/max", token, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            max_user_id: linkMax,
            link_token: linkToken,
            preferred_channel: "web_cabinet",
          }),
        });
        setMe(linked);
        setNotice("Аккаунт связан с MAX. Можно продолжать в мессенджере или здесь.");
        params.delete("link_max");
        params.delete("link_token");
        const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
        window.history.replaceState({}, "", next);
      }
    } catch {
      /* профиль не критичен для списка дел */
    }
  }, [token]);

  useEffect(() => {
    // Первичная загрузка списка дел при появлении токена.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on auth ready
    void loadCases();
  }, [loadCases]);

  useEffect(() => {
    if (!token) {
      ensureCaseRef.current = false;
      const t = window.setTimeout(() => setCasesReady(false), 0);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [token]);

  useEffect(() => {
    // Первичная загрузка профиля / link_max.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on auth ready
    void loadMe();
  }, [loadMe]);

  const openCase = useCallback(
    async (caseId: string, nextView: View = "case") => {
      if (!token) return;
      setBusy(true);
      setNotice("");
      try {
        const [caseDetail, caseMessages, consentBundle] = await Promise.all([
          apiFetch<CaseDetail>(`/api/portal/cases/${caseId}`, token),
          apiFetch<CaseMessage[]>(`/api/portal/cases/${caseId}/messages`, token),
          apiFetch<ConsentBundle>(`/api/portal/cases/${caseId}/consents`, token),
        ]);
        setSelectedId(caseId);
        setDetail(caseDetail);
        setMessages(caseMessages);
        setConsents(consentBundle);
        setView(nextView);
        void loadCases();
      } catch {
        setNotice("Нет доступа к этому делу или оно не найдено.");
      } finally {
        setBusy(false);
      }
    },
    [token, loadCases],
  );

  // P0: после первого входа сразу создать и открыть дело, если списка нет
  useEffect(() => {
    if (!token || !apiBase || !casesReady || ensureCaseRef.current) return;
    if (cases.length > 0) {
      ensureCaseRef.current = true;
      if (cases.length === 1 && view === "cases" && !selectedId) {
        const caseId = cases[0].id;
        const t = window.setTimeout(() => {
          void openCase(caseId);
        }, 0);
        return () => window.clearTimeout(t);
      }
      return;
    }
    ensureCaseRef.current = true;
    const t = window.setTimeout(() => {
      void (async () => {
        try {
          setBusy(true);
          const created = await apiFetch<{ id: string }>("/api/portal/cases", token, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          await loadCases();
          if (created?.id) {
            await openCase(created.id);
            setNotice("Дело создано. Примите согласие и загрузите документы.");
          }
        } catch {
          ensureCaseRef.current = false;
          setNotice("Не удалось создать дело. Обновите страницу или начните через MAX.");
        } finally {
          setBusy(false);
        }
      })();
    }, 0);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, casesReady, cases, openCase, loadCases]);

  async function loadPayments(caseId: string) {
    if (!token || !caseId) return;
    setBusy(true);
    try {
      const rows = await apiFetch<OrderRow[]>(`/api/portal/cases/${caseId}/orders`, token);
      setOrders(rows);
      setSelectedId(caseId);
      setView("payments");
    } catch {
      setNotice("Не удалось загрузить оплаты.");
    } finally {
      setBusy(false);
    }
  }

  async function startPayment(orderId: string) {
    if (!token || !selectedId) return;
    setPayingOrderId(orderId);
    setNotice("");
    try {
      const payload = await apiFetch<{ confirmation_url?: string; status?: string }>(
        `/api/portal/cases/${selectedId}/orders/${orderId}/pay`,
        token,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ return_channel: "web_cabinet" }),
        },
      );
      if (payload.confirmation_url) {
        window.open(payload.confirmation_url, "_blank", "noopener,noreferrer");
        setNotice("Открыта страница оплаты. После оплаты обновите список счетов.");
      } else {
        setNotice("Платёж создан. Обновите статусы чуть позже.");
      }
      const rows = await apiFetch<OrderRow[]>(
        `/api/portal/cases/${selectedId}/orders`,
        token,
      );
      setOrders(rows);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("503") || msg.toLowerCase().includes("not configured")) {
        setNotice(
          "Онлайн-оплата пока недоступна. Счёт выставит оператор вручную — статус появится здесь.",
        );
      } else {
        setNotice("Не удалось начать оплату. Попробуйте позже или напишите в чат дела.");
      }
    } finally {
      setPayingOrderId(null);
    }
  }

  async function loadResult(caseId: string) {
    if (!token) return;
    setBusy(true);
    try {
      const payload = await apiFetch<ResultPayload>(`/api/portal/cases/${caseId}/result`, token);
      setResult(payload);
      setSelectedId(caseId);
      setView("result");
    } catch {
      setNotice("Не удалось загрузить результат.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!token || cases.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("case");
    const viewParam = params.get("view");
    if (!caseId) return;
    if (!cases.some((c) => c.id === caseId)) return;
    const nextView: View =
      viewParam === "payments" || viewParam === "pay"
        ? "payments"
        : viewParam === "result"
          ? "result"
          : viewParam === "docs"
            ? "docs"
            : "case";
    // eslint-disable-next-line react-hooks/set-state-in-effect -- deep-link view from query
    if (nextView === "payments") void loadPayments(caseId);
    else if (nextView === "result") void loadResult(caseId);
    else void openCase(caseId, nextView);
    if (params.get("paid") === "1") {
      setNotice("Если оплата прошла — обновите список счетов через несколько секунд.");
    }
    params.delete("case");
    params.delete("view");
    params.delete("paid");
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
    window.history.replaceState({}, "", next);
    // один раз на вход по deep-link
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, cases]);

  function goAuthScreen(next: AuthScreen) {
    setAuthScreen(next);
    setNotice("");
    setOtpSent(false);
    setOtpCode("");
    setPassword("");
    setPasswordConfirm("");
    if (next === "login") {
      setLoginMethod("password");
      setAuthChannel("email");
    } else if (next === "max") {
      setLoginMethod("max");
      setAuthChannel("max");
      setMaxWizardStep(1);
      setMaxStep1Done(false);
      setMaxStep2Done(false);
      setMaxTicket("");
      setMaxPairCode("");
      setMaxWaitStatus("");
    } else if (next === "email_otp") {
      setLoginMethod("email_otp");
      setAuthChannel("email");
    } else if (next === "register") {
      setRegisterChannel("max");
      setAuthChannel("max");
      setMaxWizardStep(1);
      setMaxStep1Done(false);
      setMaxStep2Done(false);
    }
  }

  function chooseLoginMethod(method: LoginMethod) {
    setLoginMethod(method);
    setAuthScreen("login");
    setNotice("");
    setOtpSent(false);
    setOtpCode("");
    setPassword("");
    if (method === "max") {
      setAuthChannel("max");
      setMaxWizardStep(1);
      setMaxStep1Done(false);
      setMaxStep2Done(false);
      setMaxTicket("");
      setMaxPairCode("");
      setMaxWaitStatus("");
    } else {
      setAuthChannel("email");
    }
  }

  async function signInWithPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    if (!email.trim() || !password) {
      setNotice("Укажите почту и пароль.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) throw error;
      setNotice("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (/invalid login|invalid credentials/i.test(msg)) {
        setNotice("Неверная почта или пароль.");
      } else {
        setNotice(msg || "Не удалось войти. Проверьте данные или войдите по коду / через чат MAX.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function requestOtp(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (authChannel === "max") {
      await requestMaxOtp(Boolean(phone.trim()));
      return;
    }
    if (authChannel === "phone" && !AUTH_SMS_PUBLISHED) {
      setNotice("Вход по SMS пока недоступен. Войдите через чат MAX или почту.");
      return;
    }
    if (!supabase) {
      setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    if (!email.trim()) {
      setNotice("Укажите почту.");
      return;
    }
    setBusy(true);
    try {
      if (authChannel === "email") {
        const { error } = await supabase.auth.signInWithOtp({
          email: email.trim(),
          options: {
            shouldCreateUser: authScreen === "register",
            emailRedirectTo: `${CABINET_PUBLIC_URL}/`,
          },
        });
        if (error) throw error;
      } else if (AUTH_SMS_PUBLISHED) {
        const normalized = phone.replace(/[^\d+]/g, "");
        const { error } = await supabase.auth.signInWithOtp({
          phone: normalized,
          options: { shouldCreateUser: true },
        });
        if (error) throw error;
      } else {
        throw new Error("sms_archived");
      }
      setOtpSent(true);
      setNotice("Код отправлен на почту. Введите его ниже.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      const code =
        err && typeof err === "object" && "code" in err
          ? String((err as { code?: string }).code || "")
          : "";
      if (/rate limit|over_email/i.test(msg) || code.includes("rate_limit")) {
        setNotice(
          "Слишком много запросов. Подождите несколько минут и проверьте уже пришедшее письмо.",
        );
      } else if (
        /phone_provider|unsupported phone|sms|sms_archived/i.test(msg) ||
        code === "phone_provider_disabled"
      ) {
        setNotice("Вход по SMS пока недоступен. Войдите через чат MAX или почту.");
      } else if (/signups not allowed|user not found|unable to find/i.test(msg)) {
        setNotice("Аккаунт не найден. Зарегистрируйтесь или войдите через чат MAX.");
      } else {
        setNotice(
          authChannel === "email"
            ? "Не удалось отправить код. Проверьте адрес и попробуйте снова."
            : "Не удалось отправить код. Войдите через чат MAX или почту.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  async function requestPasswordReset(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!supabase) {
      setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    if (!email.trim()) {
      setNotice("Укажите почту.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: `${CABINET_PUBLIC_URL}/?mode=recover`,
      });
      if (error) throw error;
      setOtpSent(true);
      setNotice(
        "Если аккаунт с такой почтой есть, мы отправили письмо со ссылкой и кодом для смены пароля.",
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (/rate limit|over_email/i.test(msg)) {
        setNotice("Слишком много запросов. Подождите несколько минут.");
      } else {
        setNotice("Не удалось отправить письмо. Проверьте адрес и попробуйте снова.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function verifyEmailOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    if (!otpCode.trim()) {
      setNotice("Введите код из письма.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const otpType =
        authScreen === "recover" || recoveryMode
          ? ("recovery" as const)
          : authScreen === "register"
            ? ("signup" as const)
            : ("email" as const);
      const { error } = await supabase.auth.verifyOtp({
        email: email.trim(),
        token: otpCode.trim(),
        type: otpType,
      });
      if (error) {
        // fallback: часть проектов шлёт email OTP как type email и при регистрации
        if (otpType !== "email") {
          const second = await supabase.auth.verifyOtp({
            email: email.trim(),
            token: otpCode.trim(),
            type: "email",
          });
          if (second.error) throw error;
        } else {
          throw error;
        }
      }
      setOtpSent(false);
      setOtpCode("");
      if (authScreen === "recover") setRecoveryMode(true);
      setNotice(
        authScreen === "recover" || recoveryMode
          ? "Код принят. Задайте новый пароль."
          : "Код принят. Задайте пароль для личного кабинета.",
      );
    } catch {
      setNotice("Неверный или просроченный код.");
    } finally {
      setBusy(false);
    }
  }

  async function saveCabinetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    if (password.length < MIN_PASSWORD_LEN) {
      setNotice(`Пароль не короче ${MIN_PASSWORD_LEN} символов.`);
      return;
    }
    if (password !== passwordConfirm) {
      setNotice("Пароли не совпадают.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const { data, error } = await supabase.auth.updateUser({
        password,
        data: { password_set: true },
      });
      if (error) throw error;
      setPassword("");
      setPasswordConfirm("");
      setRecoveryMode(false);
      if (data.user) {
        setSession((prev) =>
          prev
            ? {
                ...prev,
                user: data.user,
              }
            : prev,
        );
      }
      setNotice("Пароль сохранён. Добро пожаловать в личный кабинет.");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось сохранить пароль.");
    } finally {
      setBusy(false);
    }
  }

  async function requestMaxOtp(withPhone = false) {
    if (!apiBase) {
      setNotice("API кабинета не настроен.");
      return;
    }
    if (withPhone && !phone.trim()) {
      setNotice("Укажите телефон из дела или нажмите вход без номера.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/portal/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(withPhone ? { phone } : {}),
      });
      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
        ticket?: string;
        pair_code?: string;
        max_bot_url?: string;
        message?: string;
        status?: string;
      };
      if (!response.ok) {
        const detail =
          typeof body.detail === "string"
            ? body.detail
            : "Не удалось начать вход через чат MAX.";
        throw new Error(detail);
      }
      setMaxTicket(body.ticket || "");
      setMaxPairCode(body.pair_code || "");
      setMaxWaitStatus(body.status || "pending_pair");
      if (body.max_bot_url) setMaxBotUrl(chatUrlOnly(body.max_bot_url));
      setOtpSent(true);
      setMaxWizardStep(3);
      setNotice(body.message || `Ожидаем подтверждение в чате MAX…`);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось начать вход через чат MAX.");
    } finally {
      setBusy(false);
    }
  }

  function openMaxChat() {
    // Не уводим вкладку кабинета. Ссылка без startapp; фокус сразу возвращаем сюда.
    const url = chatUrlOnly(maxBotUrl);
    const popup = window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => {
      try {
        window.focus();
      } catch {
        /* ignore */
      }
      // Если ОС уже открыла приложение MAX, служебная вкладка max.ru часто не нужна
      try {
        popup?.close();
      } catch {
        /* ignore */
      }
    }, 600);
    setMaxStep1Done(true);
    setMaxWizardStep(2);
    setNotice(
      `Оставайтесь на ${AUTH_COPY.loginPage} в ${AUTH_COPY.browser}. В чате MAX нажмите «Начать», затем вернитесь сюда.`,
    );
  }

  function markChatOpenedWithoutBrowser() {
    setMaxStep1Done(true);
    setMaxWizardStep(2);
    setNotice(
      `Хорошо. В чате MAX нажмите «Начать», затем вернитесь на ${AUTH_COPY.loginPage}.`,
    );
  }

  function markMaxStarted() {
    setMaxStep2Done(true);
    setMaxWizardStep(3);
    setNotice("");
  }

  function resetMaxWizard() {
    setOtpSent(false);
    setMaxTicket("");
    setMaxPairCode("");
    setMaxWaitStatus("");
    setNotice("");
    setMaxWizardStep(maxStep2Done ? 3 : maxStep1Done ? 2 : 1);
  }

  // ПК ждёт подтверждение кнопки в MAX на телефоне
  useEffect(() => {
    if (
      !supabase ||
      !apiBase ||
      !maxTicket ||
      session ||
      authChannel !== "max" ||
      !otpSent
    ) {
      return;
    }
    let cancelled = false;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const response = await fetch(
            `${apiBase}/api/portal/auth/otp/poll?ticket=${encodeURIComponent(maxTicket)}`,
          );
          const body = (await response.json().catch(() => ({}))) as {
            status?: string;
            token_hash?: string;
            type?: "email" | "sms";
            message?: string;
          };
          if (cancelled) return;
          if (body.status) setMaxWaitStatus(body.status);
          if (body.message) setNotice(body.message);
          if (body.status === "approved" && body.token_hash) {
            const { error } = await supabase.auth.verifyOtp({
              token_hash: body.token_hash,
              type: body.type || "email",
            });
            if (error) throw error;
            setOtpSent(false);
            setMaxTicket("");
            setMaxPairCode("");
            setNotice("");
          }
          if (body.status === "expired") {
            setNotice(body.message || "Время подтверждения истекло. Начните вход снова.");
          }
        } catch (err) {
          if (!cancelled) {
            setNotice(err instanceof Error ? err.message : "Ошибка ожидания входа.");
          }
        }
      })();
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [supabase, maxTicket, session, authChannel, otpSent]);

  async function acceptConsent() {
    if (!token || !selectedId) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/cases/${selectedId}/consents`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: "pdn-v1" }),
      });
      setNotice("Согласие на обработку ПДн зафиксировано.");
      await openCase(selectedId, view === "docs" ? "docs" : "case");
    } catch {
      setNotice("Не удалось сохранить согласие.");
    } finally {
      setBusy(false);
    }
  }

  async function acceptContract() {
    if (!token || !selectedId) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/cases/${selectedId}/contract-acceptances`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer_version: "offer-v1" }),
      });
      setNotice("Акцепт оферты и индивидуального заказа зафиксирован.");
      await openCase(selectedId, "docs");
    } catch {
      setNotice("Не удалось сохранить акцепт оферты.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(file: File, docType?: string) {
    if (!token || !selectedId) return;
    if (!detail?.consent_accepted) {
      setNotice("Сначала подтвердите согласие на обработку ПДн.");
      setView("docs");
      return;
    }
    const allowed = ["application/pdf", "image/jpeg", "image/png"];
    if (!allowed.includes(file.type)) {
      setNotice("Допустимы только PDF, JPG и PNG.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      if (docType) form.append("doc_type", docType);
      await apiFetch(`/api/portal/cases/${selectedId}/documents`, token, {
        method: "POST",
        body: form,
      });
      setNotice("Файл загружен в защищённое хранилище.");
      await openCase(selectedId, docType === "sfr_decision" ? "result" : "case");
      if (docType === "sfr_decision") await loadResult(selectedId);
    } catch (error) {
      const text = error instanceof Error ? error.message : "";
      setNotice(
        text.includes("consent")
          ? "Сначала подтвердите согласие на обработку ПДн."
          : "Не удалось загрузить файл.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function openSignedUrl(documentId: string) {
    if (!token || !selectedId) return;
    try {
      const payload = await apiFetch<{ url: string; expires_in: number }>(
        `/api/portal/cases/${selectedId}/documents/${documentId}/signed-url`,
        token,
        { method: "POST" },
      );
      window.open(payload.url, "_blank", "noopener,noreferrer");
      setNotice(`Ссылка действует ${payload.expires_in} сек.`);
    } catch {
      setNotice("Не удалось получить временную ссылку.");
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !selectedId || !messageBody.trim()) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/cases/${selectedId}/messages`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: messageBody.trim() }),
      });
      setMessageBody("");
      const next = await apiFetch<CaseMessage[]>(
        `/api/portal/cases/${selectedId}/messages`,
        token,
      );
      setMessages(next);
    } catch {
      setNotice("Не удалось отправить сообщение.");
    } finally {
      setBusy(false);
    }
  }

  async function setPreferredChannel(channel: PreferredChannel) {
    if (!token) return;
    setBusy(true);
    try {
      const profile = await apiFetch<PortalMe>("/api/portal/me/preferences", token, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferred_channel: channel }),
      });
      setMe(profile);
      setNotice(
        channel === "max_miniapp"
          ? "Предпочтение: MAX. Уведомления по умолчанию — в мессенджер."
          : channel === "web_cabinet"
            ? "Предпочтение: веб-кабинет."
            : "Предпочтение канала сброшено.",
      );
    } catch {
      setNotice("Не удалось сохранить предпочтение канала.");
    } finally {
      setBusy(false);
    }
  }

  async function runCheck() {
    if (!token || !selectedId) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await apiFetch<{
        ok: boolean;
        message: string;
        pipeline_status?: string;
        findings?: { type: string; detail: string }[];
      }>(`/api/portal/cases/${selectedId}/run`, token, { method: "POST" });
      setNotice(result.message || "Проверка запрошена.");
      await openCase(selectedId, "case");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось запустить проверку.");
    } finally {
      setBusy(false);
    }
  }

  function renderMaxWizard(title: string, lead?: string) {
    const stepState = (n: 1 | 2 | 3): "done" | "current" | "todo" => {
      if (n === 1) return maxStep1Done ? "done" : maxWizardStep === 1 ? "current" : "todo";
      if (n === 2)
        return maxStep2Done ? "done" : maxWizardStep === 2 ? "current" : "todo";
      if (otpSent && maxWaitStatus === "approved") return "done";
      return maxWizardStep === 3 || otpSent ? "current" : "todo";
    };
    return (
      <>
        <p className="lead lead-compact">
          <strong>{title}</strong>
          {lead ? (
            <>
              <br />
              {lead}
            </>
          ) : null}
        </p>
        <div className="max-wizard">
          <ol className="max-wizard-steps" aria-label="Шаги входа">
            {(
              [
                { n: 1 as const, title: `Откройте ${AUTH_COPY.chatMax}` },
                { n: 2 as const, title: `В чате MAX нажмите «Начать»` },
                {
                  n: 3 as const,
                  title: `Код со страницы входа → в ${AUTH_COPY.chatMax}`,
                },
              ] as const
            ).map((s) => {
              const st = stepState(s.n);
              return (
                <li key={s.n} className={`max-wizard-step max-wizard-step--${st}`}>
                  <button
                    type="button"
                    className="max-wizard-step-btn"
                    aria-current={maxWizardStep === s.n ? "step" : undefined}
                    onClick={() => {
                      setMaxWizardStep(s.n);
                      setNotice("");
                    }}
                  >
                    <span className="max-wizard-marker" aria-hidden="true">
                      {st === "done" ? "✓" : st === "current" ? "●" : "○"}
                    </span>
                    <span className="max-wizard-step-num">{s.n}.</span>
                    <span className="max-wizard-step-title">{s.title}</span>
                  </button>
                </li>
              );
            })}
          </ol>
          <div className="max-wizard-panel">
            {maxWizardStep === 1 ? (
              <>
                <h2>Шаг 1. Откройте {AUTH_COPY.chatMax}</h2>
                <p className="muted">
                  Не уходите с {AUTH_COPY.loginPage}. Переключитесь в уже открытый{" "}
                  {AUTH_COPY.chatMax} (поиск {MAX_BOT_HANDLE}) — {AUTH_COPY.browser} с кабинетом
                  останется здесь.
                </p>
                <button type="button" onClick={markChatOpenedWithoutBrowser}>
                  {AUTH_COPY.openedChatBtn}
                </button>
                <button type="button" className="ghost" onClick={openMaxChat}>
                  Открыть ссылку на чат MAX
                </button>
                <p className="hint">
                  Ссылка может на секунду открыть max.ru — сразу вернитесь на{" "}
                  {AUTH_COPY.loginPage} в {AUTH_COPY.browser}.
                </p>
              </>
            ) : null}
            {maxWizardStep === 2 ? (
              <>
                <h2>Шаг 2. Начните диалог в чате MAX</h2>
                <p>
                  В чате MAX нажмите <strong>«Начать»</strong> (или «Старт»). Затем
                  вернитесь на <strong>{AUTH_COPY.loginPage}</strong> в {AUTH_COPY.browser} — не
                  на страницу «Запустить бота».
                </p>
                <button type="button" onClick={markMaxStarted}>
                  {AUTH_COPY.pressedStartBtn}
                </button>
                <button type="button" className="ghost" onClick={openMaxChat}>
                  Снова открыть ссылку на чат MAX
                </button>
              </>
            ) : null}
            {maxWizardStep === 3 ? (
              <>
                <h2>Шаг 3. Код со страницы входа</h2>
                {!otpSent ? (
                  <>
                    <p className="muted">
                      Нажмите «{AUTH_COPY.showCodeBtn}» — код появится здесь. Посмотрите на код и
                      отправьте его в {AUTH_COPY.chatMax}. Лишние окна {AUTH_COPY.browser} не
                      нужны.
                    </p>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void requestMaxOtp(false)}
                    >
                      {AUTH_COPY.showCodeBtn}
                    </button>
                  </>
                ) : (
                  <>
                    <p className="max-wizard-status" role="status">
                      {maxWaitStatus === "pending_confirm"
                        ? "Код принят в чате MAX. Завершаем вход…"
                        : maxWaitStatus === "pending_pair"
                          ? `Смотрите код ниже и отправьте его в ${AUTH_COPY.chatMax}`
                          : "Ожидаем…"}
                    </p>
                    {maxWaitStatus === "pending_pair" && maxPairCode ? (
                      <p>
                        Код для {AUTH_COPY.chatMax}:{" "}
                        <strong className="max-pair-code">{maxPairCode}</strong>
                        <br />
                        <span className="muted">
                          Введите его в чате MAX, оставаясь на {AUTH_COPY.loginPage}.
                        </span>
                      </p>
                    ) : (
                      <p className="muted">
                        После кода кабинет откроется на этой же {AUTH_COPY.loginPage}.
                      </p>
                    )}
                    <button type="button" className="ghost" onClick={resetMaxWizard}>
                      Начать заново
                    </button>
                  </>
                )}
                <details className="max-wizard-extra">
                  <summary>У меня уже есть номер в деле</summary>
                  <form onSubmit={requestOtp} style={{ marginTop: "0.75rem" }}>
                    <label htmlFor="phone-max">Телефон из дела</label>
                    <input
                      id="phone-max"
                      type="tel"
                      placeholder="+79001234567"
                      value={phone}
                      onChange={(event) => setPhone(event.target.value)}
                      required
                      autoComplete="tel"
                    />
                    <button type="submit" disabled={busy}>
                      Запросить подтверждение на этот номер
                    </button>
                  </form>
                </details>
              </>
            ) : null}
          </div>
        </div>
      </>
    );
  }

  // После входа/регистрации без пароля — назначить пароль кабинета
  if (session && (recoveryMode || !hasPasswordSet(session))) {
    return (
      <main className="auth-layout">
        <section className="card auth-card">
          <p className="eyebrow">
            <img className="brand-logo" src="/logo-light.png" width={40} height={40} alt="" />
            Проверка стажа
          </p>
          <h1>{recoveryMode ? "Новый пароль" : "Пароль личного кабинета"}</h1>
          <p className="lead lead-compact">
            {recoveryMode
              ? "Задайте новый пароль для входа по почте."
              : "При первой регистрации назначьте пароль — им можно входить с компьютера без чата MAX."}
          </p>
          <form className="auth-form" onSubmit={saveCabinetPassword}>
            <label htmlFor="new-password">Пароль</label>
            <input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={MIN_PASSWORD_LEN}
              autoComplete="new-password"
            />
            <label htmlFor="new-password-confirm">Повторите пароль</label>
            <input
              id="new-password-confirm"
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              minLength={MIN_PASSWORD_LEN}
              autoComplete="new-password"
            />
            <button type="submit" disabled={busy}>
              Сохранить пароль
            </button>
          </form>
          {notice && <p className="notice">{notice}</p>}
          <p className="hint">
            <button
              type="button"
              className="linkish"
              onClick={() => void supabase?.auth.signOut()}
            >
              Выйти
            </button>
          </p>
        </section>
      </main>
    );
  }

  if (!session) {
    const showMax =
      (authScreen === "login" && loginMethod === "max") ||
      (authScreen === "register" && registerChannel === "max");
    const showLoginMethods = authScreen === "login";

    return (
      <main className="auth-layout">
        <section className={`card auth-card ${showMax ? "auth-wizard" : ""}`}>
          <p className="eyebrow">
            <img className="brand-logo" src="/logo-light.png" width={40} height={40} alt="" />
            Проверка стажа
          </p>
          <h1>Личный кабинет</h1>

          {authScreen !== "recover" ? (
            <div className="auth-mode-tabs" role="tablist" aria-label="Режим">
              <button
                type="button"
                className={authScreen === "login" ? "tab active" : "tab"}
                onClick={() => goAuthScreen("login")}
              >
                Вход
              </button>
              <button
                type="button"
                className={authScreen === "register" ? "tab active" : "tab"}
                onClick={() => goAuthScreen("register")}
              >
                Регистрация
              </button>
            </div>
          ) : null}

          {showLoginMethods ? (
            <>
              <p className="lead lead-compact">Выберите способ входа:</p>
              <div className="auth-method-list" role="tablist" aria-label="Способ входа">
                <button
                  type="button"
                  className={
                    loginMethod === "password" ? "auth-method active" : "auth-method"
                  }
                  onClick={() => chooseLoginMethod("password")}
                >
                  <strong>Пароль</strong>
                  <span>Ранее заданный пароль на {AUTH_COPY.loginPage}</span>
                </button>
                <button
                  type="button"
                  className={loginMethod === "max" ? "auth-method active" : "auth-method"}
                  onClick={() => chooseLoginMethod("max")}
                >
                  <strong>Код в {AUTH_COPY.chatMax}</strong>
                  <span>Подтверждение входа в чате MAX</span>
                </button>
                <button
                  type="button"
                  className={
                    loginMethod === "email_otp" ? "auth-method active" : "auth-method"
                  }
                  onClick={() => chooseLoginMethod("email_otp")}
                >
                  <strong>Временный код на {AUTH_COPY.email}</strong>
                  <span>Одноразовый код письмом на {AUTH_COPY.email}</span>
                </button>
              </div>
            </>
          ) : null}

          {showLoginMethods && loginMethod === "password" ? (
            <>
              <form className="auth-form" onSubmit={signInWithPassword}>
                <label htmlFor="login-email">Почта</label>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
                <label htmlFor="login-password">Пароль</label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button type="submit" disabled={busy}>
                  Войти
                </button>
              </form>
              <p className="auth-links">
                <button type="button" className="linkish" onClick={() => goAuthScreen("recover")}>
                  Забыли пароль?
                </button>
              </p>
            </>
          ) : null}

          {showLoginMethods && loginMethod === "email_otp" ? (
            <>
              <p className="muted">
                На почту придёт временный одноразовый код. Введите его ниже.
              </p>
              {!otpSent ? (
                <form className="auth-form" onSubmit={requestOtp}>
                  <label htmlFor="otp-email">Почта</label>
                  <input
                    id="otp-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                  <button type="submit" disabled={busy}>
                    Получить временный код
                  </button>
                </form>
              ) : (
                <form className="auth-form" onSubmit={verifyEmailOtp}>
                  <label htmlFor="login-otp">Код из письма</label>
                  <input
                    id="login-otp"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    required
                  />
                  <button type="submit" disabled={busy}>
                    Войти по коду
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void requestOtp()}
                  >
                    Отправить ещё раз
                  </button>
                </form>
              )}
            </>
          ) : null}

          {authScreen === "register" && registerChannel === "email" ? (
            <>
              <p className="lead lead-compact">
                Регистрация: код придёт на почту, затем вы сами назначите пароль.
              </p>
              <div className="tabs" role="tablist" aria-label="Канал регистрации">
                <button
                  type="button"
                  className="tab"
                  onClick={() => {
                    setRegisterChannel("max");
                    setAuthChannel("max");
                    setMaxWizardStep(1);
                    setMaxStep1Done(false);
                    setMaxStep2Done(false);
                  }}
                >
                  Чат MAX
                </button>
                <button
                  type="button"
                  className="tab active"
                  onClick={() => setRegisterChannel("email")}
                >
                  Почта
                </button>
              </div>
              {!otpSent ? (
                <form className="auth-form" onSubmit={requestOtp}>
                  <label htmlFor="reg-email">Почта</label>
                  <input
                    id="reg-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                  <button type="submit" disabled={busy}>
                    Получить код на почту
                  </button>
                </form>
              ) : (
                <form className="auth-form" onSubmit={verifyEmailOtp}>
                  <p className="muted">
                    Код отправлен на <strong>{email}</strong>. Введите его ниже.
                  </p>
                  <label htmlFor="reg-otp">Код из письма</label>
                  <input
                    id="reg-otp"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    required
                  />
                  <button type="submit" disabled={busy}>
                    Подтвердить код
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void requestOtp()}
                  >
                    Отправить код ещё раз
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      setOtpSent(false);
                      setOtpCode("");
                    }}
                  >
                    Изменить почту
                  </button>
                </form>
              )}
            </>
          ) : null}

          {authScreen === "register" && registerChannel === "max"
            ? (
              <>
                <div className="tabs" role="tablist" aria-label="Канал регистрации">
                  <button type="button" className="tab active">
                    Чат MAX
                  </button>
                  <button
                    type="button"
                    className="tab"
                    onClick={() => {
                      setRegisterChannel("email");
                      setAuthChannel("email");
                      setOtpSent(false);
                    }}
                  >
                    Почта
                  </button>
                </div>
                {renderMaxWizard(
                  "Регистрация через чат MAX.",
                  `После подтверждения в ${AUTH_COPY.chatMax} назначьте себе пароль на ${AUTH_COPY.loginPage}.`,
                )}
              </>
            )
            : null}

          {authScreen === "register" && registerChannel === "max" ? (
            <p className="hint auth-alt-hint">
              <button
                type="button"
                className="linkish"
                onClick={() => {
                  setRegisterChannel("email");
                  setAuthChannel("email");
                  setOtpSent(false);
                }}
              >
                Регистрация по почте
              </button>
              {" · "}
              <button type="button" className="linkish" onClick={() => goAuthScreen("login")}>
                Уже есть аккаунт? Войти
              </button>
            </p>
          ) : null}

          {authScreen === "recover" ? (
            <>
              <p className="lead lead-compact">
                Укажите почту — пришлём ссылку и код для восстановления пароля.
              </p>
              {!otpSent ? (
                <form className="auth-form" onSubmit={requestPasswordReset}>
                  <label htmlFor="recover-email">Почта</label>
                  <input
                    id="recover-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                  <button type="submit" disabled={busy}>
                    Восстановить пароль
                  </button>
                </form>
              ) : (
                <form className="auth-form" onSubmit={verifyEmailOtp}>
                  <p className="muted">
                    Если письмо пришло с кодом — введите его. Или откройте ссылку из письма.
                  </p>
                  <label htmlFor="recover-otp">Код из письма</label>
                  <input
                    id="recover-otp"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                  />
                  <button type="submit" disabled={busy || !otpCode.trim()}>
                    Подтвердить код
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void requestPasswordReset()}
                  >
                    Отправить ещё раз
                  </button>
                </form>
              )}
              <p className="hint">
                <button type="button" className="linkish" onClick={() => goAuthScreen("login")}>
                  ← Вернуться ко входу
                </button>
              </p>
            </>
          ) : null}

          {showLoginMethods && loginMethod === "max"
            ? renderMaxWizard(
                "Вход через чат MAX.",
                `Код смотрите на ${AUTH_COPY.loginPage} в ${AUTH_COPY.browser} и отправьте его в ${AUTH_COPY.chatMax}.`,
              )
            : null}

          {notice && <p className="notice">{notice}</p>}
          <p className="hint auth-site-hint">
            Нужна проверка стажа без кабинета?{" "}
            <a href={`${SITE_URL}/#zayavka`} target="_blank" rel="noreferrer">
              Оставить заявку на сайте
            </a>
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-layout">
      <header>
        <div className="brand-block">
          <img className="brand-logo" src="/logo-light.png" width={40} height={40} alt="" />
          <div>
            <strong>Проверка стажа</strong>
            <span>Личный кабинет</span>
          </div>
        </div>
        <div className="header-actions">
          <a
            className="ghost"
            href={
              selectedId
                ? `${DEFAULT_MAX_MINIAPP}${
                    DEFAULT_MAX_MINIAPP.includes("?") ? "&" : "?"
                  }startapp=case_${selectedId.slice(0, 8)}`
                : me?.max_miniapp_url || DEFAULT_MAX_MINIAPP
            }
            target="_blank"
            rel="noopener noreferrer"
          >
            Продолжить в чате MAX
          </a>
          <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
            Выйти
          </button>
        </div>
      </header>

      <section className="warning" role="note">
        Решение принимает СФР. Результат не гарантирован.
      </section>

      <section className="card channel-card">
        <h2>Канал работы</h2>
        <p className="muted">
          Можно вести одно дело и в чате MAX, и в браузере.
          {me?.max_linked
            ? " Чат MAX уже привязан."
            : " Чтобы связать чат MAX — откройте ссылку из мини-приложения."}
        </p>
        <div className="tabs" role="group" aria-label="Предпочтительный канал">
          <button
            type="button"
            className={me?.preferred_channel === "web_cabinet" ? "tab active" : "tab"}
            disabled={busy}
            onClick={() => void setPreferredChannel("web_cabinet")}
          >
            Веб-кабинет
          </button>
          <button
            type="button"
            className={me?.preferred_channel === "max_miniapp" ? "tab active" : "tab"}
            disabled={busy}
            onClick={() => void setPreferredChannel("max_miniapp")}
          >
            MAX
          </button>
          <button
            type="button"
            className={me?.preferred_channel === "unset" || !me ? "tab active" : "tab"}
            disabled={busy}
            onClick={() => void setPreferredChannel("unset")}
          >
            Не задан
          </button>
        </div>
      </section>

      {selectedId && (
        <nav className="case-nav" aria-label="Разделы дела">
          <button type="button" className="ghost" onClick={() => setView("cases")}>
            ← К списку дел
          </button>
          <button
            type="button"
            className={view === "case" ? "tab active" : "tab"}
            onClick={() => void openCase(selectedId, "case")}
          >
            Дело
          </button>
          <button
            type="button"
            className={view === "docs" ? "tab active" : "tab"}
            onClick={() => void openCase(selectedId, "docs")}
          >
            Документы и согласия
          </button>
          <button
            type="button"
            className={view === "payments" ? "tab active" : "tab"}
            onClick={() => void loadPayments(selectedId)}
          >
            Оплаты
          </button>
          <button
            type="button"
            className={view === "result" ? "tab active" : "tab"}
            onClick={() => void loadResult(selectedId)}
          >
            Результат
          </button>
        </nav>
      )}

      {view === "cases" && (
        <section>
          <h1>Мои дела</h1>
          <p className="lead">Клиент и законный представитель видят только доступные им дела.</p>
          {cases.length === 0 ? (
            <p>
              {busy
                ? "Создаём ваше дело…"
                : "Дел пока нет. Обновите страницу — дело создастся автоматически."}
            </p>
          ) : (
            <ul className="case-list">
              {cases.map((caseItem) => (
                <li key={caseItem.id}>
                  <button
                    type="button"
                    className="case-card-button"
                    onClick={() => void openCase(caseItem.id)}
                  >
                    <strong>Дело {shortId(caseItem.id)}</strong>
                    <span>Статус: {labelStatus(caseItem.b2c_status)} · этап {labelStatus(caseItem.pipeline_status)}</span>
                    <span>
                      Ответственный:{" "}
                      {caseItem.expert_assigned ? "сотрудник назначен" : "ожидает назначения"}
                    </span>
                    <span>
                      Ближайшее действие: {caseItem.next_action ?? "нет открытых пунктов"}
                    </span>
                    <span>
                      Непрочитанных сообщений: {caseItem.unread_messages}
                      {caseItem.checklist_open_count > 0
                        ? ` · открытых пунктов: ${caseItem.checklist_open_count}`
                        : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {view === "case" && detail && (
        <section className="stack">
          <h1>Дело {shortId(detail.id)}</h1>
          <p>
            Текущий этап:{" "}
            <strong>{detail.status_label || labelStatus(detail.pipeline_status)}</strong>
            {" · "}
            {labelStatus(detail.b2c_status)}
          </p>
          {detail.status_hint && <p className="hint">{detail.status_hint}</p>}
          {detail.next_action && (
            <p>
              Ближайшее действие: <strong>{detail.next_action}</strong>
            </p>
          )}
          <p>
            Ответственный сотрудник:{" "}
            {detail.expert_assigned ? "назначен" : "ещё не назначен"}
          </p>

          <div className="panel accent">
            <h2>Проверка документов</h2>
            <p className="hint">
              Запускает сверку / передаёт дело специалисту. Подачи в СФР от вашего имени нет.
            </p>
            <button type="button" onClick={() => void runCheck()} disabled={busy || !detail.consent_accepted}>
              Запустить проверку
            </button>
            {!detail.consent_accepted && (
              <p className="hint">Сначала подтвердите согласие на обработку ПДн.</p>
            )}
          </div>

          {!detail.consent_accepted && (
            <div className="panel accent">
              <h2>Согласие на обработку ПДн</h2>
              <p>
                Подтвердите согласие до загрузки документов.{" "}
                <a href={`${SITE_URL}/soglasie/`} target="_blank" rel="noreferrer">
                  Текст согласия
                </a>
              </p>
              <button type="button" onClick={() => void acceptConsent()} disabled={busy}>
                Подтверждаю согласие
              </button>
            </div>
          )}

          <div className="panel">
            <h2>Возможные расхождения</h2>
            {detail.pipeline_error && <p className="notice">{detail.pipeline_error}</p>}
            {!detail.findings?.length ? (
              <p>Пока нет findings. Загрузите документы и запустите проверку.</p>
            ) : (
              <ul className="plain-list">
                {detail.findings.map((f, idx) => (
                  <li key={`${f.type}-${idx}`}>
                    <strong>{f.type}</strong>
                    {f.detail ? `: ${f.detail}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <h2>Персональный чек-лист</h2>
            {detail.checklist_items.length === 0 ? (
              <p>Чек-лист появится после аудита документов.</p>
            ) : (
              <ul className="plain-list">
                {detail.checklist_items.map((item) => (
                  <li key={item.id}>
                    <strong>{item.title}</strong>
                    <span>
                      {item.status} · {item.owner === "client" ? "ваше действие" : "эксперт"}
                      {item.due_at ? ` · до ${new Date(item.due_at).toLocaleDateString("ru-RU")}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <h2>Требуемые документы</h2>
            {detail.required_documents.length === 0 ? (
              <p>Сейчас нет открытых запросов документов.</p>
            ) : (
              <ul className="plain-list">
                {detail.required_documents.map((item) => (
                  <li key={item.id}>{item.title}</li>
                ))}
              </ul>
            )}
            <label className="file-label">
              Загрузить PDF / JPG / PNG
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                disabled={busy || !detail.consent_accepted}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void uploadDocument(file);
                  event.target.value = "";
                }}
              />
            </label>
            {!detail.consent_accepted && (
              <p className="hint">Загрузка недоступна без согласия на обработку ПДн.</p>
            )}
            {detail.documents.length > 0 && (
              <ul className="plain-list">
                {detail.documents.map((doc) => (
                  <li key={doc.id}>
                    <button type="button" className="linkish" onClick={() => void openSignedUrl(doc.id)}>
                      {doc.storage_path.split("/").pop() ?? doc.id}
                    </button>
                    <span className="hint"> · временная ссылка</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <h2>Черновик заявления</h2>
            {detail.draft ? (
              <>
                <p>
                  <strong>{detail.draft.title ?? "Черновик"}</strong>
                  {detail.draft.needs_human_review ? " · требуется проверка эксперта" : ""}
                </p>
                <pre className="draft">{detail.draft.body}</pre>
              </>
            ) : (
              <p>Черновик появится после подготовки экспертом.</p>
            )}
          </div>

          <div className="panel">
            <h2>Как подать самостоятельно</h2>
            <p>{detail.submission_instruction}</p>
            <p className="hint">Кнопки «Подать в СФР от вашего имени» в кабинете нет и не будет.</p>
          </div>

          <div className="panel">
            <h2>Сообщения и уведомления</h2>
            <ul className="messages">
              {messages.length === 0 && <li>Сообщений пока нет.</li>}
              {messages.map((message) => (
                <li key={message.id} className={message.author_kind === "client" ? "mine" : ""}>
                  <span className="meta">
                    {message.author_kind} · {new Date(message.created_at).toLocaleString("ru-RU")}
                  </span>
                  <p>{message.body}</p>
                </li>
              ))}
            </ul>
            <form className="message-form" onSubmit={sendMessage}>
              <label htmlFor="message">Новое сообщение</label>
              <textarea
                id="message"
                rows={3}
                value={messageBody}
                onChange={(event) => setMessageBody(event.target.value)}
                maxLength={4000}
                required
              />
              <button type="submit" disabled={busy}>
                Отправить
              </button>
            </form>
          </div>
        </section>
      )}

      {view === "docs" && detail && consents && (
        <section className="stack">
          <h1>Документы и согласия</h1>
          <div className="panel">
            <h2>Согласие на обработку ПДн</h2>
            <p>
              <a href={consents.consent_url} target="_blank" rel="noreferrer">
                Текст согласия
              </a>
              {" · "}
              <a href={consents.pdn_url} target="_blank" rel="noreferrer">
                Политика ПДн
              </a>
            </p>
            {detail.consent_accepted ? (
              <p className="ok">Согласие принято.</p>
            ) : (
              <button type="button" onClick={() => void acceptConsent()} disabled={busy}>
                Подтвердить согласие
              </button>
            )}
            <ul className="plain-list">
              {consents.consents.map((row) => (
                <li key={row.id}>
                  версия {row.version} · {new Date(row.accepted_at).toLocaleString("ru-RU")}
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>Оферта и индивидуальный заказ</h2>
            <p>
              <a href={consents.offer_url} target="_blank" rel="noreferrer">
                Публичная оферта
              </a>
            </p>
            <button type="button" onClick={() => void acceptContract()} disabled={busy}>
              Акцептовать оферту и заказ
            </button>
            <ul className="plain-list">
              {consents.contract_acceptances.length === 0 && <li>Акцептов пока нет.</li>}
              {consents.contract_acceptances.map((row) => (
                <li key={row.id}>
                  оферта {row.offer_version} · {new Date(row.accepted_at).toLocaleString("ru-RU")}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {view === "payments" && selectedId && (
        <section className="stack">
          <h1>Оплаты</h1>
          <p className="lead">
            Диагностика и сопровождение — фиксированные счета. Post-payment появляется только после
            подтверждения результата.
          </p>
          {orders.length === 0 ? (
            <p>Счетов пока нет.</p>
          ) : (
            <ul className="case-list">
              {orders.map((order) => {
                const isPost = order.package_code.startsWith("SF_");
                const canPay = order.status === "pending" || order.status === "awaiting_payment";
                return (
                  <li key={order.id}>
                    <strong>{PACKAGE_LABELS[order.package_code] ?? order.package_code}</strong>
                    <span>
                      {order.amount_rub} ₽ · статус {order.status}
                      {isPost ? " · post-payment" : ""}
                    </span>
                    {(order.payments ?? []).map((payment) => (
                      <span key={payment.id}>
                        Платёж: {payment.status}
                        {payment.paid_at
                          ? ` · ${new Date(payment.paid_at).toLocaleDateString("ru-RU")}`
                          : ""}
                      </span>
                    ))}
                    {canPay ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={payingOrderId === order.id}
                        onClick={() => void startPayment(order.id)}
                      >
                        {payingOrderId === order.id ? "Создаём платёж…" : "Оплатить онлайн"}
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
          <p className="hint">
            Если онлайн-оплата недоступна, оператор отметит оплату вручную — статус обновится здесь.
          </p>
        </section>
      )}

      {view === "result" && result && selectedId && (
        <section className="stack">
          <h1>Результат</h1>
          <p className="warning inline">{result.warning}</p>
          <div className="panel">
            <h2>Решение СФР</h2>
            <label className="file-label">
              Загрузить решение (PDF / JPG / PNG)
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                disabled={busy || !detail?.consent_accepted}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void uploadDocument(file, "sfr_decision");
                  event.target.value = "";
                }}
              />
            </label>
          </div>
          <div className="panel">
            <h2>Размер пенсии и выплата</h2>
            {result.evidence ? (
              <ul className="plain-list">
                <li>Прежний размер: {result.evidence.monthly_before_rub ?? "—"} ₽</li>
                <li>Новый размер: {result.evidence.monthly_after_rub ?? "—"} ₽</li>
                <li>Единовременная выплата: {result.evidence.lump_sum_rub ?? "—"} ₽</li>
                <li>
                  Подтверждение эксперта:{" "}
                  {result.evidence.confirmed_at
                    ? new Date(result.evidence.confirmed_at).toLocaleString("ru-RU")
                    : "ещё не подтверждено"}
                </li>
              </ul>
            ) : (
              <p>Данные результата появятся после загрузки решения и проверки экспертом.</p>
            )}
          </div>
          <div className="panel">
            <h2>Расчёт вознаграждения</h2>
            <ul className="plain-list">
              <li>10% от ЕДВ: {result.success_fee.sf_lump} ₽</li>
              <li>50% прибавки × 3 мес.: {result.success_fee.sf_month} ₽</li>
              <li>
                <strong>Итого: {result.success_fee.sf_total} ₽</strong>
              </li>
            </ul>
            <p className="hint">{result.post_payment_note}</p>
          </div>
        </section>
      )}

      {notice && <p className="notice">{notice}</p>}
      {busy && <p className="hint">Загрузка…</p>}
    </main>
  );
}
