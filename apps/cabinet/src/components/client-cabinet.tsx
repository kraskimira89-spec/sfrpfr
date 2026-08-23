"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { humanCaseStatus, loadStatusLabels } from "@/lib/status-labels";
import { labelOrderStatus, labelPackage, labelPaymentStatus } from "../../../../shared/ui-labels";

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
  doc_type_label?: string | null;
  created_at?: string;
  filename?: string | null;
  content_preview?: string | null;
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
/** Единый вход: max | register | password | email_otp | recover. SMS не публикуем. */
type AuthScreen = "max" | "register" | "password" | "email_otp" | "recover";

/** SMS-вход не публикуем (см. apps/cabinet/src/archive/auth-sms.md). */
const AUTH_SMS_PUBLISHED = false;
const MIN_PASSWORD_LEN = 8;

function hasPasswordSet(session: Session | null): boolean {
  if (!session?.user) return false;
  const meta = session.user.user_metadata as Record<string, unknown> | undefined;
  return meta?.password_set === true;
}

/** Короткий понятный номер дела из UUID (стабильный). Совпадает с хвостом ПС-YY-ИИ-NNNNNN. */
function caseNumberFromId(caseId: string): string {
  const hex = String(caseId || "").replace(/-/g, "").slice(-5);
  const n = Number.parseInt(hex, 16);
  if (!Number.isFinite(n) || n <= 0) return "—";
  return String(n);
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
const SITE_URL = "https://proverkastaza.ru";
const CABINET_PUBLIC_URL =
  process.env.NEXT_PUBLIC_CABINET_PUBLIC_URL ?? "https://cabinet.proverkastaza.ru";
const DEFAULT_MAX_CHAT = "https://max.ru/id8905998693_1_bot";
const DEFAULT_MAX_MINIAPP = "https://max.ru/id8905998693_1_bot?startapp";

function BrandHomeLink({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      className={className ? `brand-home-link ${className}` : "brand-home-link"}
      href={SITE_URL}
      title="На главную"
      aria-label="На главную"
    >
      {children}
    </a>
  );
}

function SiteNavButton({ className }: { className?: string }) {
  return (
    <a
      className={className ? `cabinet-nav-btn ${className}` : "cabinet-nav-btn"}
      href={SITE_URL}
    >
      На сайт
    </a>
  );
}

function SiteReturnPanel() {
  return (
    <a className="auth-return-panel" href={SITE_URL}>
      <span className="auth-return-panel__title">Вернуться на сайт</span>
      <span className="auth-return-panel__hint">proverkastaza.ru</span>
    </a>
  );
}

/** Единые термины: чат MAX / браузер / страница входа / почта (как в боте). */
const AUTH_COPY = {
  chatMax: "чат MAX",
  browser: "браузер",
  loginPage: "страница входа",
  email: "почта",
  showCodeBtn: "Показать код здесь",
  getCodeInBrowser: "Получить код для входа",
  openChatBtn: "Открыть чат MAX",
  confirmBtn: "Подтвердить вход в браузере",
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

function packageLabel(code: string) {
  return labelPackage(code);
}

type HomeStepKey = "consent" | "upload" | "check";

function resolveHomeStep(detail: {
  consent_accepted: boolean;
  documents: { id: string }[];
}): { current: HomeStepKey; nowNeed: string } {
  if (!detail.consent_accepted) {
    return { current: "consent", nowNeed: "подтвердить согласие" };
  }
  if (detail.documents.length === 0) {
    return { current: "upload", nowNeed: "загрузить документы" };
  }
  return { current: "check", nowNeed: "отправить документы на проверку" };
}

function authorLabel(kind: string) {
  if (kind === "client") return "Вы";
  if (kind === "representative") return "Представитель";
  if (kind === "system") return "Система";
  if (kind === "expert" || kind === "operator" || kind === "staff") return "Специалист";
  return kind;
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
  const [authScreen, setAuthScreen] = useState<AuthScreen>("max");
  const [authChannel, setAuthChannel] = useState<AuthChannel>("max");
  /** true — OTP на почту может создать пользователя (первый раз без MAX). */
  const [emailCreateUser, setEmailCreateUser] = useState(false);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [fullName, setFullName] = useState("");
  /** Контакты уже из заявки с сайта — не спрашиваем повторно. */
  const [fromLeadPrefill, setFromLeadPrefill] = useState(false);
  const [editLeadContacts, setEditLeadContacts] = useState(false);
  const [registerConsent, setRegisterConsent] = useState(false);
  const [maxTicket, setMaxTicket] = useState("");
  const [maxVerifyTicket, setMaxVerifyTicket] = useState("");
  const [maxWaitStatus, setMaxWaitStatus] = useState("");
  const [maxBotUrl, setMaxBotUrl] = useState(DEFAULT_MAX_CHAT);
  const [maxLinkBusy, setMaxLinkBusy] = useState(false);
  const getCodeOnceRef = useRef(false);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [passwordDeferred, setPasswordDeferred] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.sessionStorage.getItem("sfrfr_pwd_later") === "1";
    } catch {
      return false;
    }
  });
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
  const [savingPassword, setSavingPassword] = useState(false);
  const [payingOrderId, setPayingOrderId] = useState<string | null>(null);
  const [me, setMe] = useState<PortalMe | null>(null);
  const [youAreRepresentative, setYouAreRepresentative] = useState(false);
  const [representatives, setRepresentatives] = useState<
    { user_id: string; email?: string | null; full_name?: string | null }[]
  >([]);
  const ensureCaseRef = useRef(false);

  useEffect(() => {
    if (!apiBase) return;
    void loadStatusLabels(apiBase);
  }, []);

  const token = session?.access_token;
  const needsPasswordGate = Boolean(
    session &&
      (recoveryMode || (!hasPasswordSet(session) && !passwordDeferred)),
  );

  function deferPassword() {
    try {
      window.sessionStorage.setItem("sfrfr_pwd_later", "1");
    } catch {
      /* ignore */
    }
    setPasswordDeferred(true);
    setNotice("");
  }

  function openPasswordSetup() {
    try {
      window.sessionStorage.removeItem("sfrfr_pwd_later");
    } catch {
      /* ignore */
    }
    setPasswordDeferred(false);
    setNotice("");
  }

  // Query: ?mode=login|register|recover; ?channel=max; ?verify_ticket=
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mode = (params.get("mode") || "").toLowerCase();
    const channel = (params.get("channel") || "").toLowerCase();
    const qEmail = (params.get("email") || "").trim();
    const qPhone = (params.get("phone") || "").trim();
    const qName = (params.get("name") || "").trim();
    const fromLead =
      params.get("from_lead") === "1" ||
      (mode === "register" && Boolean(qEmail || qPhone));
    const wantMax =
      channel === "max" ||
      params.get("register")?.toLowerCase() === "max" ||
      Boolean(params.get("verify_ticket"));
    const t = window.setTimeout(() => {
      if (qEmail) setEmail(qEmail);
      if (qPhone) setPhone(qPhone);
      if (qName) setFullName(qName);
      if (fromLead && (qEmail || qPhone)) {
        setFromLeadPrefill(true);
        setEditLeadContacts(false);
      }
      if (mode === "recover") {
        setAuthScreen("recover");
        setAuthChannel("email");
        return;
      }
      if (mode === "register") {
        setAuthScreen("register");
        setEmailCreateUser(true);
        setAuthChannel(qEmail && !qPhone ? "email" : qPhone && !qEmail ? "max" : "email");
        return;
      }
      if (mode === "password" || (mode === "login" && !wantMax && channel === "email")) {
        setAuthScreen("password");
        setAuthChannel("email");
        return;
      }
      if (mode === "login") {
        setAuthScreen("max");
        setAuthChannel("max");
        return;
      }
      setAuthScreen("max");
      setAuthChannel("max");
    }, 0);
    return () => window.clearTimeout(t);
  }, []);

  // Ссылка из MAX с verify_ticket — сразу форма ввода кода
  useEffect(() => {
    if (!apiBase || session || getCodeOnceRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const vt = (params.get("verify_ticket") || "").trim();
    if (!vt) return;
    getCodeOnceRef.current = true;
    const t = window.setTimeout(() => {
      setMaxVerifyTicket(vt);
      setOtpSent(true);
      setAuthScreen("max");
      setAuthChannel("max");
      setNotice("Введите код из чата MAX.");
      params.delete("verify_ticket");
      const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
      window.history.replaceState({}, "", next);
    }, 50);
    return () => window.clearTimeout(t);
  }, [apiBase, session]);

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
    // Первичная загрузка списка дел при появлении токена (после пароля).
    if (needsPasswordGate) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on auth ready
    void loadCases();
  }, [loadCases, needsPasswordGate]);

  useEffect(() => {
    if (!token) {
      ensureCaseRef.current = false;
      const t = window.setTimeout(() => setCasesReady(false), 0);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [token]);

  useEffect(() => {
    // Первичная загрузка профиля / link_max (после пароля).
    if (needsPasswordGate) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on auth ready
    void loadMe();
  }, [loadMe, needsPasswordGate]);

  // На экране пароля не блокируем кнопку глобальным busy от MAX/дел
  useEffect(() => {
    if (!needsPasswordGate) return;
    const t = window.setTimeout(() => setBusy(false), 0);
    return () => window.clearTimeout(t);
  }, [needsPasswordGate]);

  const openCase = useCallback(
    async (caseId: string, nextView: View = "case") => {
      if (!token) return;
      setBusy(true);
      setNotice("");
      try {
        const [caseDetail, caseMessages, consentBundle, reps] = await Promise.all([
          apiFetch<CaseDetail>(`/api/portal/cases/${caseId}`, token),
          apiFetch<CaseMessage[]>(`/api/portal/cases/${caseId}/messages`, token),
          apiFetch<ConsentBundle>(`/api/portal/cases/${caseId}/consents`, token),
          apiFetch<{
            items: { user_id: string; email?: string | null; full_name?: string | null }[];
            you_are_representative: boolean;
          }>(`/api/portal/cases/${caseId}/representatives`, token).catch(() => ({
            items: [],
            you_are_representative: false,
          })),
        ]);
        setSelectedId(caseId);
        setDetail(caseDetail);
        setMessages(caseMessages);
        setConsents(consentBundle);
        setRepresentatives(reps.items || []);
        setYouAreRepresentative(Boolean(reps.you_are_representative));
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

  // P0: после пароля сразу создать и открыть дело, если списка нет
  useEffect(() => {
    if (needsPasswordGate) return;
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
  }, [token, casesReady, cases, openCase, loadCases, needsPasswordGate]);

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
    setEmailCreateUser(next === "register");
    setMaxVerifyTicket("");
    if (next === "register") {
      setRegisterConsent(false);
    }
    if (next === "max") {
      setAuthChannel("max");
      resetMaxWizard();
    } else if (next === "register") {
      setAuthChannel("email");
      resetMaxWizard();
    } else if (next === "password" || next === "email_otp" || next === "recover") {
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
            shouldCreateUser: emailCreateUser,
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
          : emailCreateUser
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
    setSavingPassword(true);
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
      setSavingPassword(false);
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
        verify_ticket?: string;
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
      setMaxVerifyTicket(body.verify_ticket || "");
      setMaxWaitStatus(body.status || "pending_pair");
      if (body.max_bot_url) setMaxBotUrl(chatUrlOnly(body.max_bot_url));
      setOtpSent(true);
      setNotice(body.message || `Ожидаем подтверждение в чате MAX…`);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось начать вход через чат MAX.");
    } finally {
      setBusy(false);
    }
  }

  async function requestRegister(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!registerConsent) {
      setNotice("Отметьте согласие с СОПД — без него регистрацию продолжить нельзя.");
      return;
    }
    const hasEmail = Boolean(email.trim());
    const hasPhone = Boolean(phone.trim());
    if (!hasEmail && !hasPhone) {
      setNotice("Укажите почту или телефон — на него придёт проверочный код.");
      return;
    }
    if (hasEmail) {
      setAuthChannel("email");
      setEmailCreateUser(true);
      setBusy(true);
      setNotice("");
      try {
        if (!supabase) {
          setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
          return;
        }
        const { error } = await supabase.auth.signInWithOtp({
          email: email.trim(),
          options: {
            shouldCreateUser: true,
            emailRedirectTo: `${CABINET_PUBLIC_URL}/`,
            data: fullName.trim() ? { full_name: fullName.trim() } : undefined,
          },
        });
        if (error) throw error;
        setOtpSent(true);
        setMaxVerifyTicket("");
        setNotice("Код отправлен на почту. Введите его ниже.");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "";
        if (/rate limit|over_email/i.test(msg)) {
          setNotice("Слишком много запросов. Подождите несколько минут.");
        } else {
          setNotice("Не удалось отправить код на почту. Проверьте адрес.");
        }
      } finally {
        setBusy(false);
      }
      return;
    }
    // Только телефон → код в MAX (если номер связан) иначе — вход через чат MAX
    setAuthChannel("max");
    setEmailCreateUser(false);
    setBusy(true);
    setNotice("");
    try {
      if (!apiBase) {
        setNotice("API кабинета не настроен.");
        return;
      }
      const response = await fetch(`${apiBase}/api/portal/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: phone.trim() }),
      });
      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
        ticket?: string;
        verify_ticket?: string;
        max_bot_url?: string;
        message?: string;
        status?: string;
      };
      if (response.ok) {
        setMaxTicket(body.ticket || "");
        setMaxVerifyTicket(body.verify_ticket || "");
        setMaxWaitStatus(body.status || "pending_confirm");
        if (body.max_bot_url) setMaxBotUrl(chatUrlOnly(body.max_bot_url));
        setOtpSent(true);
        setNotice(
          body.message ||
            "Код отправлен в MAX. Введите его на этой странице.",
        );
        return;
      }
      // Первый раз без привязки MAX: открыть чат и получить код там
      const fallback = await fetch(`${apiBase}/api/portal/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const fb = (await fallback.json().catch(() => ({}))) as {
        detail?: string;
        ticket?: string;
        max_bot_url?: string;
        message?: string;
        status?: string;
      };
      if (!fallback.ok) {
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : typeof fb.detail === "string"
              ? fb.detail
              : "Не удалось начать регистрацию через MAX.",
        );
      }
      setMaxTicket(fb.ticket || "");
      setMaxVerifyTicket("");
      setMaxWaitStatus(fb.status || "pending_pair");
      const bot = chatUrlOnly(fb.max_bot_url || maxBotUrl);
      if (fb.max_bot_url) setMaxBotUrl(bot);
      setOtpSent(true);
      window.open(bot, "_blank", "noopener,noreferrer");
      setNotice(
        fb.message ||
          "Откройте чат MAX, нажмите «Получить код для входа» и введите код на этой странице.",
      );
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось начать регистрацию.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyMaxSiteOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || !apiBase) return;
    if (!otpCode.trim()) {
      setNotice("Введите код из чата MAX.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/portal/auth/otp/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticket: maxVerifyTicket || "",
          code: otpCode.trim(),
        }),
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
            : "Неверный или устаревший код.",
        );
      }
      const { error } = await supabase.auth.verifyOtp({
        token_hash: body.token_hash || "",
        type: body.type || "email",
      });
      if (error) throw error;
      setOtpSent(false);
      setMaxTicket("");
      setMaxVerifyTicket("");
      setNotice("");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось войти по коду.");
    } finally {
      setBusy(false);
    }
  }

  function openMaxChat() {
    const url = chatUrlOnly(maxBotUrl);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async function startMaxLogin() {
    openMaxChat();
    await requestMaxOtp(false);
  }

  function resetMaxWizard() {
    setOtpSent(false);
    setMaxTicket("");
    setMaxVerifyTicket("");
    setMaxWaitStatus("");
    setOtpCode("");
    setNotice("");
    getCodeOnceRef.current = false;
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
            verify_ticket?: string;
          };
          if (cancelled) return;
          if (body.status) setMaxWaitStatus(body.status);
          if (body.message) setNotice(body.message);
          if (body.verify_ticket) setMaxVerifyTicket(body.verify_ticket);
          if (body.status === "approved" && body.token_hash) {
            const { error } = await supabase.auth.verifyOtp({
              token_hash: body.token_hash,
              type: body.type || "email",
            });
            if (error) throw error;
            setOtpSent(false);
            setMaxTicket("");
            setMaxVerifyTicket("");
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
        body: JSON.stringify({ version: "pdn-consent-2026-08-22" }),
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
        body: JSON.stringify({ offer_version: "offer-2026-08-14" }),
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
      setNotice("Сначала подтвердите согласие.");
      setView("case");
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
      const payload = await apiFetch<{
        payment_receipt?: { status?: string; message?: string };
      }>(`/api/portal/cases/${selectedId}/documents`, token, {
        method: "POST",
        body: form,
      });
      const receipt = payload.payment_receipt;
      if (receipt?.status === "confirmed") {
        setNotice(receipt.message || "Оплата подтверждена по чеку.");
        await loadPayments(selectedId);
        setView("payments");
        await openCase(selectedId, "payments");
      } else if (receipt?.message) {
        setNotice(receipt.message);
        await openCase(selectedId, docType === "payment_receipt" ? "payments" : "case");
      } else {
        setNotice("Файл загружен. Список и краткое содержание — ниже.");
        await openCase(selectedId, docType === "sfr_decision" ? "result" : "case");
      }
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

  function renderMaxWizard() {
    const awaitingMaxConfirm =
      maxWaitStatus === "pending_pair" ||
      maxWaitStatus === "pending_confirm" ||
      (!maxWaitStatus && !maxVerifyTicket);
    const needsCodeOnSite = maxWaitStatus === "code_sent";

    return (
      <>
        <p className="lead lead-compact">
          Войдите через чат MAX — подтвердите вход в приложении, кабинет откроется здесь.
        </p>
        <div className="max-wizard max-wizard--actions">
          {!otpSent ? (
            <>
              <button
                type="button"
                className="max-action-btn"
                disabled={busy}
                onClick={() => void startMaxLogin()}
              >
                Войти через MAX
              </button>
              <ol className="max-login-steps">
                <li>Откроется чат MAX</li>
                <li>Нажмите «Получить код для входа»</li>
                <li>Кабинет откроется на этой странице</li>
              </ol>
            </>
          ) : awaitingMaxConfirm && !needsCodeOnSite ? (
            <>
              <p className="max-wizard-status" role="status">
                {maxWaitStatus === "pending_confirm"
                  ? "Подтвердите вход в чате MAX — кабинет откроется автоматически"
                  : "Откройте чат MAX и нажмите «Получить код для входа»"}
              </p>
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={() => openMaxChat()}
              >
                Открыть чат MAX
              </button>
              <button type="button" className="ghost" onClick={resetMaxWizard}>
                Начать заново
              </button>
            </>
          ) : (
            <>
              <p className="max-wizard-status" role="status">
                Код отправлен в чат MAX — введите его здесь
              </p>
              <form className="auth-form" onSubmit={verifyMaxSiteOtp}>
                <label htmlFor="max-site-otp">Код из MAX</label>
                <input
                  id="max-site-otp"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  required
                />
                <button type="submit" disabled={busy}>
                  Войти по коду
                </button>
              </form>
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={() => openMaxChat()}
              >
                Открыть чат MAX снова
              </button>
              <button type="button" className="ghost" onClick={resetMaxWizard}>
                Начать заново
              </button>
            </>
          )}
        </div>
      </>
    );
  }

  // После входа — пароль по желанию (кроме восстановления)
  if (needsPasswordGate) {
    return (
      <main className="auth-layout auth-layout--split">
        <div className="auth-split">
          <section className="card auth-card">
            <p className="eyebrow">
              <BrandHomeLink>
                <img
                  className="brand-logo"
                  src="/logo-light.png"
                  width={40}
                  height={40}
                  alt="Проверка стажа"
                />
                Проверка стажа
              </BrandHomeLink>
            </p>
            <h1>{recoveryMode ? "Новый пароль" : "Пароль — по желанию"}</h1>
            <p className="lead lead-compact">
              {recoveryMode
                ? "Задайте новый пароль для входа по почте."
                : "Можно сразу перейти к делу. Пароль пригодится позже для входа без чата MAX."}
            </p>
            {!recoveryMode ? (
              <button type="button" className="max-action-btn" onClick={deferPassword}>
                Перейти к делу без пароля
              </button>
            ) : null}
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
              <button type="submit" disabled={savingPassword}>
                {savingPassword ? "Сохраняем…" : "Сохранить пароль"}
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
          <SiteReturnPanel />
        </div>
      </main>
    );
  }

  if (!session) {
    const showMax = authScreen === "max";
    const loginTabActive = authScreen !== "register";

    return (
      <main className="auth-layout auth-layout--split">
        <div className="auth-split">
        <section className={`card auth-card ${showMax ? "auth-wizard" : ""}`}>
          <p className="eyebrow">
            <BrandHomeLink>
              <img
                className="brand-logo"
                src="/logo-light.png"
                width={40}
                height={40}
                alt="Проверка стажа"
              />
              Проверка стажа
            </BrandHomeLink>
          </p>
          <h1>Личный кабинет</h1>

          <div className="auth-tabs" role="tablist" aria-label="Вход или регистрация">
            <button
              type="button"
              role="tab"
              id="auth-tab-login"
              aria-selected={loginTabActive}
              className={loginTabActive ? "auth-tab active" : "auth-tab"}
              onClick={() => goAuthScreen("max")}
            >
              Вход
            </button>
            <button
              type="button"
              role="tab"
              id="auth-tab-register"
              aria-selected={!loginTabActive}
              className={!loginTabActive ? "auth-tab active" : "auth-tab"}
              onClick={() => goAuthScreen("register")}
            >
              Регистрация
            </button>
          </div>

          {authScreen === "max" ? (
            <>
              {renderMaxWizard()}
              <div className="auth-alt-hint">
                <p className="auth-alt-label">Другие способы входа</p>
                <div className="auth-alt-list" role="group" aria-label="Другие способы входа">
                  <button
                    type="button"
                    className="auth-alt-btn"
                    onClick={() => goAuthScreen("password")}
                  >
                    По паролю
                  </button>
                  <button
                    type="button"
                    className="auth-alt-btn"
                    onClick={() => {
                      setEmailCreateUser(false);
                      goAuthScreen("email_otp");
                    }}
                  >
                    Код на почту
                  </button>
                </div>
              </div>
            </>
          ) : null}

          {authScreen === "register" ? (
            <>
              <p className="lead lead-compact">
                {fromLeadPrefill && !editLeadContacts
                  ? "Данные из заявки уже подставлены. Отметьте согласие — проверочный код придёт на почту или в MAX."
                  : "Регистрация: укажите почту или телефон. Проверочный код придёт на почту или в MAX — введите его на этой странице."}
              </p>
              {!otpSent ? (
                <form className="auth-form" onSubmit={requestRegister}>
                  {fromLeadPrefill && !editLeadContacts ? (
                    <div className="auth-prefill-summary" aria-live="polite">
                      {fullName.trim() ? (
                        <p>
                          <span className="auth-prefill-label">Имя</span>
                          <strong>{fullName.trim()}</strong>
                        </p>
                      ) : null}
                      {email.trim() ? (
                        <p>
                          <span className="auth-prefill-label">Почта</span>
                          <strong>{email.trim()}</strong>
                        </p>
                      ) : null}
                      {phone.trim() ? (
                        <p>
                          <span className="auth-prefill-label">Телефон</span>
                          <strong>{phone.trim()}</strong>
                        </p>
                      ) : null}
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => setEditLeadContacts(true)}
                      >
                        Изменить контакты
                      </button>
                    </div>
                  ) : (
                    <>
                      <label htmlFor="reg-name">Имя</label>
                      <input
                        id="reg-name"
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        autoComplete="name"
                      />
                      <label htmlFor="reg-email">Электронная почта</label>
                      <input
                        id="reg-email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        autoComplete="email"
                        placeholder="по желанию"
                      />
                      <label htmlFor="reg-phone">Телефон</label>
                      <input
                        id="reg-phone"
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        autoComplete="tel"
                        placeholder="по желанию"
                      />
                      <p className="hint">Нужна почта или телефон — хотя бы одно поле.</p>
                    </>
                  )}
                  <label className="auth-consent" htmlFor="reg-consent">
                    <input
                      id="reg-consent"
                      type="checkbox"
                      checked={registerConsent}
                      onChange={(e) => setRegisterConsent(e.target.checked)}
                      required
                    />
                    <span>
                      Согласен с{" "}
                      <a
                        href={`${SITE_URL}/soglasie/`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        СОПД
                      </a>
                    </span>
                  </label>
                  <button type="submit" disabled={busy || !registerConsent}>
                    Получить код
                  </button>
                </form>
              ) : maxVerifyTicket || authChannel === "max" ? (
                <form className="auth-form" onSubmit={verifyMaxSiteOtp}>
                  <p className="max-wizard-status" role="status">
                    Код придёт в чат MAX — введите его здесь
                  </p>
                  <label htmlFor="reg-max-otp">Код из MAX</label>
                  <input
                    id="reg-max-otp"
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
                    onClick={() => {
                      openMaxChat();
                      void requestRegister();
                    }}
                  >
                    Открыть MAX / отправить ещё раз
                  </button>
                </form>
              ) : authChannel === "email" ? (
                <form className="auth-form" onSubmit={verifyEmailOtp}>
                  <label htmlFor="reg-email-otp">Код из письма</label>
                  <input
                    id="reg-email-otp"
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
                    onClick={() => void requestRegister()}
                  >
                    Отправить ещё раз
                  </button>
                </form>
              ) : (
                <button type="button" className="ghost" onClick={resetMaxWizard}>
                  Начать заново
                </button>
              )}
              <p className="auth-links">
                <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                  ← Войти через MAX
                </button>
              </p>
            </>
          ) : null}

          {authScreen === "password" ? (
            <>
              <p className="lead lead-compact">Вход по почте и паролю.</p>
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
                {" · "}
                <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                  ← Войти через MAX
                </button>
              </p>
            </>
          ) : null}

          {authScreen === "email_otp" ? (
            <>
              <p className="lead lead-compact">
                {emailCreateUser
                  ? "Первый раз без MAX: код на почту, затем назначите пароль."
                  : "Одноразовый код письмом на почту."}
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
                    Получить код
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
              <p className="hint">
                <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                  ← Войти через MAX
                </button>
              </p>
            </>
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
                <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                  ← Войти через MAX
                </button>
              </p>
            </>
          ) : null}

          {notice && <p className="notice">{notice}</p>}
          <div className="auth-site-hint">
            <p className="hint">Нужна проверка стажа без кабинета?</p>
            <a
              className="button-link auth-site-hint__btn"
              href={`${SITE_URL}/#zayavka`}
              target="_blank"
              rel="noreferrer"
            >
              Оставить заявку на сайте
            </a>
          </div>
        </section>
          <SiteReturnPanel />
        </div>
      </main>
    );
  }

  const maxChatHref =
    selectedId
      ? `${DEFAULT_MAX_MINIAPP}${DEFAULT_MAX_MINIAPP.includes("?") ? "&" : "?"}startapp=case_${selectedId.slice(0, 8)}`
      : me?.max_miniapp_url || DEFAULT_MAX_MINIAPP;
  const home =
    detail && view === "case" ? resolveHomeStep(detail) : null;
  const stepDone = {
    consent: Boolean(detail?.consent_accepted),
    upload: Boolean(detail && detail.documents.length > 0),
    check: Boolean(
      detail &&
        detail.documents.length > 0 &&
        detail.consent_accepted &&
        !["new", "intake", "documents_requested", ""].includes(
          (detail.pipeline_status || "").toLowerCase(),
        ),
    ),
  };

  return (
    <main className="app-layout">
      <header>
        <div className="brand-block">
          <BrandHomeLink className="brand-home-link--header">
            <img
              className="brand-logo"
              src="/logo-light.png"
              width={40}
              height={40}
              alt="Проверка стажа"
            />
            <div>
              <strong>Проверка стажа</strong>
              <span>Личный кабинет</span>
            </div>
          </BrandHomeLink>
        </div>
        <div className="header-actions">
          <SiteNavButton />
          <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
            Выйти
          </button>
        </div>
      </header>

      {selectedId && view !== "cases" && view !== "case" ? (
        <nav className="case-nav case-nav--back" aria-label="Назад">
          <button type="button" className="ghost" onClick={() => void openCase(selectedId, "case")}>
            ← К вашему делу
          </button>
        </nav>
      ) : null}

      {cases.length > 1 && view !== "cases" && view === "case" ? (
        <p className="hint">
          <button type="button" className="linkish" onClick={() => setView("cases")}>
            Другие дела
          </button>
        </p>
      ) : null}

      {view === "cases" && (
        <section>
          <h1>Ваши дела</h1>
          {cases.length === 0 ? (
            <div className="panel accent">
              <p>{busy ? "Готовим ваше дело…" : "Готовим ваше дело…"}</p>
              <button type="button" onClick={() => void loadCases()} disabled={busy}>
                Обновить
              </button>
            </div>
          ) : (
            <ul className="case-list">
              {cases.map((caseItem) => (
                <li key={caseItem.id}>
                  <button
                    type="button"
                    className="case-card-button"
                    onClick={() => void openCase(caseItem.id)}
                  >
                    <strong>Дело ПС-{caseNumberFromId(caseItem.id)}</strong>
                    <span>
                      {humanCaseStatus(caseItem.pipeline_status, caseItem.b2c_status)}
                    </span>
                    <span>
                      Сейчас нужно: {caseItem.next_action ?? "открыть дело"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {view === "case" && detail && home && (
        <section className="stack">
          <h1>Дело ПС-{caseNumberFromId(detail.id)}</h1>
          {youAreRepresentative ? (
            <p className="ok">Вы законный представитель по этому делу</p>
          ) : null}
          <p className="status-line">
            {humanCaseStatus(detail.pipeline_status, detail.b2c_status)}
          </p>
          {(detail.pipeline_status || "").toLowerCase() === "completed" ? (
            <div className="panel accent" style={{ marginTop: "0.75rem" }}>
              <p>
                Если захотите — можно сформулировать короткий отзыв о нашей работе
                (необязательно). Публикуете вы сами на Яндексе.
              </p>
              <p style={{ marginTop: "0.75rem", display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                <a
                  className="button-link"
                  href="https://proverkastaza.ru/anketa-otzyv/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Сформулировать отзыв
                </a>
                <a
                  className="button-link"
                  href="https://proverkastaza.ru/otzyv/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Сразу форма Яндекса
                </a>
              </p>
            </div>
          ) : null}
          <p className="now-need">
            Сейчас нужно: <strong>{home.nowNeed}</strong>
          </p>

          <ol className="home-steps">
            <li className={stepDone.consent ? "done" : home.current === "consent" ? "current" : ""}>
              <span className="mark" aria-hidden>
                {stepDone.consent ? "✓" : home.current === "consent" ? "●" : "○"}
              </span>
              Шаг 1. Согласие
            </li>
            <li className={stepDone.upload ? "done" : home.current === "upload" ? "current" : ""}>
              <span className="mark" aria-hidden>
                {stepDone.upload ? "✓" : home.current === "upload" ? "●" : "○"}
              </span>
              Шаг 2. Загрузить документы
            </li>
            <li className={stepDone.check ? "done" : home.current === "check" ? "current" : ""}>
              <span className="mark" aria-hidden>
                {stepDone.check ? "✓" : home.current === "check" ? "●" : "○"}
              </span>
              Шаг 3. Отправить на проверку
            </li>
          </ol>

          {home.current === "consent" && (
            <div className="panel accent">
              <h2>Подтвердите согласие</h2>
              <p>
                Нужно до загрузки документов.{" "}
                <a href={`${SITE_URL}/soglasie/`} target="_blank" rel="noreferrer">
                  Текст согласия
                </a>
              </p>
              <button type="button" onClick={() => void acceptConsent()} disabled={busy}>
                Даю согласие на обработку персональных данных
              </button>
            </div>
          )}

          {home.current === "upload" && (
            <div className="panel accent">
              <h2>Загрузить документы</h2>
              <p className="hint">Выписка ИЛС — PDF или фото (JPG / PNG).</p>
              {detail.required_documents.length > 0 && (
                <ul className="plain-list">
                  {detail.required_documents.map((item) => (
                    <li key={item.id}>{item.title}</li>
                  ))}
                </ul>
              )}
              <label className="file-label">
                Загрузить выписку ИЛС (PDF или фото)
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                  disabled={busy}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void uploadDocument(file);
                    event.target.value = "";
                  }}
                />
              </label>
            </div>
          )}

          {home.current === "check" && (
            <div className="panel accent">
              <h2>Отправить на проверку</h2>
              <p className="hint">
                Документы уйдут специалисту. Подачи в СФР от вашего имени нет.
              </p>
              <button type="button" onClick={() => void runCheck()} disabled={busy}>
                Отправить документы на проверку
              </button>
              <label className="file-label">
                Добавить ещё документ
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                  disabled={busy}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void uploadDocument(file);
                    event.target.value = "";
                  }}
                />
              </label>
            </div>
          )}

          <div className="docs-uploaded" aria-live="polite">
            <p className="docs-count">
              Уже загружено: {detail.documents.length}{" "}
              {detail.documents.length === 1
                ? "документ"
                : detail.documents.length > 1 && detail.documents.length < 5
                  ? "документа"
                  : "документов"}
            </p>
            {detail.documents.length > 0 ? (
              <ul className="doc-list">
                {detail.documents.map((doc) => {
                  const name =
                    (doc.filename || "").trim() ||
                    doc.storage_path.split("/").pop() ||
                    doc.id;
                  const when = doc.created_at
                    ? new Date(doc.created_at).toLocaleString("ru-RU", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "";
                  const typeLabel = (doc.doc_type_label || "").trim();
                  const preview = (doc.content_preview || "").trim();
                  return (
                    <li key={doc.id} className="doc-list-item">
                      <button
                        type="button"
                        className="linkish doc-list-name"
                        onClick={() => void openSignedUrl(doc.id)}
                      >
                        {name}
                      </button>
                      <p className="doc-list-meta">
                        {[typeLabel, when].filter(Boolean).join(" · ") || "файл принят"}
                      </p>
                      <p className="doc-list-preview">
                        {preview ||
                          "Краткое содержание появится после распознавания текста. Файл уже сохранён."}
                      </p>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="hint">Пока файлов нет — загрузите выписку ИЛС или трудовую книжку.</p>
            )}
          </div>

          <div className="home-actions">
            <a className="secondary" href="#messages">
              Написать специалисту
            </a>
            <a className="ghost" href={maxChatHref} target="_blank" rel="noopener noreferrer">
              Открыть чат MAX
            </a>
          </div>

          {(detail.documents ?? []).some((d) =>
            `${d.doc_type || ""}`.toLowerCase().includes("diagnosis_report"),
          ) && (
            <div className="panel">
              <h2>Результат диагностики</h2>
              <p className="hint">
                Информационно-документарный разбор. Не является решением СФР и не гарантирует
                перерасчёт. Скачайте PDF и при необходимости покажите родственнику.
              </p>
              <ul className="doc-list">
                {(detail.documents ?? [])
                  .filter((d) =>
                    `${d.doc_type || ""}`.toLowerCase().includes("diagnosis_report"),
                  )
                  .map((doc) => {
                    const name =
                      (doc.filename || "").trim() ||
                      doc.storage_path.split("/").pop() ||
                      doc.id;
                    return (
                      <li key={doc.id} className="doc-list-item">
                        <button
                          type="button"
                          className="linkish doc-list-name"
                          onClick={() => void openSignedUrl(doc.id)}
                        >
                          {name}
                        </button>
                        <p className="doc-list-meta">
                          {doc.doc_type_label || "Результат диагностики"}
                        </p>
                      </li>
                    );
                  })}
              </ul>
            </div>
          )}

          {(detail.findings?.length ?? 0) > 0 && (
            <div className="panel">
              <h2>Что нашли в документах</h2>
              {detail.pipeline_error && <p className="notice">{detail.pipeline_error}</p>}
              <ul className="plain-list">
                {(detail.findings ?? []).map((f, idx) => (
                  <li key={`${f.type}-${idx}`}>
                    <strong>{f.type}</strong>
                    {f.detail ? `: ${f.detail}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.checklist_items.length > 0 && (
            <div className="panel">
              <h2>Что ещё нужно сделать</h2>
              <ul className="plain-list">
                {detail.checklist_items.map((item) => (
                  <li key={item.id}>
                    <strong>{item.title}</strong>
                    {" · "}
                    <span>
                      {item.owner === "client" ? "ваше действие" : "специалист"}
                      {item.due_at
                        ? ` · до ${new Date(item.due_at).toLocaleDateString("ru-RU")}`
                        : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.draft && (
            <div className="panel">
              <h2>Проект обращения</h2>
              <p>
                <strong>{detail.draft.title ?? "Черновик"}</strong>
                {detail.draft.needs_human_review ? " · нужна проверка специалиста" : ""}
              </p>
              <pre className="draft">{detail.draft.body}</pre>
            </div>
          )}

          {detail.submission_instruction && stepDone.check && (
            <div className="panel">
              <h2>Как подать самостоятельно</h2>
              <p>{detail.submission_instruction}</p>
            </div>
          )}

          <div className="panel" id="messages">
            <h2>Написать специалисту</h2>
            <ul className="messages">
              {messages.length === 0 && <li>Сообщений пока нет.</li>}
              {messages.map((message) => (
                <li key={message.id} className={message.author_kind === "client" ? "mine" : ""}>
                  <span className="meta">
                    {authorLabel(message.author_kind)} ·{" "}
                    {new Date(message.created_at).toLocaleString("ru-RU")}
                  </span>
                  <p>{message.body}</p>
                </li>
              ))}
            </ul>
            <form className="message-form" onSubmit={sendMessage}>
              <label htmlFor="message">Ваше сообщение</label>
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

          <details className="home-more">
            <summary>Ещё</summary>
            <div className="home-more-links">
              <a className="linkish" href={maxChatHref} target="_blank" rel="noopener noreferrer">
                Продолжить в MAX
              </a>
              <button
                type="button"
                className="linkish"
                onClick={() => void loadPayments(selectedId!)}
              >
                Оплаты
              </button>
              <button
                type="button"
                className="linkish"
                onClick={() => void loadResult(selectedId!)}
              >
                Результат
              </button>
              <button
                type="button"
                className="linkish"
                onClick={() => void openCase(selectedId!, "docs")}
              >
                Согласие и договор
              </button>
              {!hasPasswordSet(session) ? (
                <button type="button" className="linkish" onClick={openPasswordSetup}>
                  Задать пароль
                </button>
              ) : null}
            </div>
            <div className="channel-prefs">
              <p className="hint">Куда удобнее получать уведомления?</p>
              <div className="channel-prefs-buttons" role="group" aria-label="Предпочтительный канал">
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
              {representatives.length > 0 ? (
                <p className="hint">
                  Представители:{" "}
                  {representatives
                    .map((r) => r.full_name || r.email || r.user_id.slice(0, 8))
                    .join(", ")}
                </p>
              ) : null}
            </div>
          </details>
        </section>
      )}

      {view === "docs" && detail && consents && (
        <section className="stack">
          <h1>Согласие и договор</h1>
          <div className="panel">
            <h2>Согласие на обработку ПДн</h2>
            <p>
              <a href={consents.consent_url} target="_blank" rel="noreferrer">
                Текст согласия
              </a>
            </p>
            <p>
              <a href={consents.pdn_url} target="_blank" rel="noreferrer">
                Политика ПДн
              </a>
            </p>
            {detail.consent_accepted ? (
              <p className="ok">Согласие принято.</p>
            ) : (
              <button type="button" onClick={() => void acceptConsent()} disabled={busy}>
                Даю согласие на обработку персональных данных
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
            <h2>Условия услуги</h2>
            <p>
              <a href={consents.offer_url} target="_blank" rel="noreferrer">
                Публичная оферта
              </a>
            </p>
            <button type="button" onClick={() => void acceptContract()} disabled={busy}>
              Принять условия услуги
            </button>
            <ul className="plain-list">
              {consents.contract_acceptances.length === 0 && <li>Пока не принято.</li>}
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
            Диагностика — фиксированный счёт. Оплата после результата появляется только после
            подтверждения.
          </p>
          {orders.length === 0 ? (
            <p>Счетов пока нет.</p>
          ) : (
            <ul className="case-list">
              {orders.map((order) => {
                const isPost = order.package_code.startsWith("SF_");
                const canPay =
                  order.status === "pending" ||
                  order.status === "awaiting_payment" ||
                  order.status === "draft";
                return (
                  <li key={order.id}>
                    <strong>{packageLabel(order.package_code)}</strong>
                    <span>
                      {order.amount_rub} ₽ · {labelOrderStatus(order.status)}
                      {isPost ? " · оплата после результата" : " · диагностика"}
                    </span>
                    {(order.payments ?? []).map((payment) => (
                      <span key={payment.id}>
                        Платёж: {labelPaymentStatus(payment.status)}
                        {payment.paid_at
                          ? ` · ${new Date(payment.paid_at).toLocaleDateString("ru-RU")}`
                          : ""}
                      </span>
                    ))}
                    {canPay ? (
                      <>
                        <button
                          type="button"
                          className="secondary"
                          disabled={payingOrderId === order.id}
                          onClick={() => void startPayment(order.id)}
                        >
                          {payingOrderId === order.id ? "Создаём платёж…" : "Оплатить онлайн"}
                        </button>
                        <label className="file-label">
                          Или прикрепить чек (PDF / JPG / PNG)
                          <input
                            type="file"
                            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                            disabled={busy || !detail?.consent_accepted}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              if (file) void uploadDocument(file, "payment_receipt");
                              event.target.value = "";
                            }}
                          />
                        </label>
                      </>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
          <p className="hint">
            Если оплатите по ссылке ЮKassa, чек присылать не нужно — статус обновится сам.
            Если переводом, прикрепите чек: сверим реквизиты и откроем следующий шаг.
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
                  Подтверждение специалиста:{" "}
                  {result.evidence.confirmed_at
                    ? new Date(result.evidence.confirmed_at).toLocaleString("ru-RU")
                    : "ещё не подтверждено"}
                </li>
              </ul>
            ) : (
              <p>Данные появятся после загрузки решения и проверки специалистом.</p>
            )}
          </div>
          <div className="panel">
            <h2>Расчёт вознаграждения</h2>
            <ul className="plain-list">
              <li>10% от единовременной выплаты: {result.success_fee.sf_lump} ₽</li>
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

      <p className="warning warning--footer" role="note">
        Решение принимает СФР. Результат не гарантирован.
      </p>
    </main>
  );
}
