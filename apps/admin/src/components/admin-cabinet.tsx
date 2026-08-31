"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import {
  labelFeedbackQuality,
  labelPackage,
  labelPipeline,
  pipelineStageOptions,
  PIPELINE_FILTER_STAGES,
  labelStaffRole,
} from "@/lib/ui-labels";
import { CasesRegistry, buildPreviewFromSummary, caseCatalogLabel } from "@/components/cases-registry";
import { FinancePanel, type FinanceOrder, type FinanceSnapshot } from "@/components/finance-panel";
import { AdminAnalyticsPanel, type AnalyticsSnapshot } from "@/components/admin-analytics-panel";
import { CaseChatPanel } from "@/components/case-chat-panel";
import { CaseFunnelMain, type StepChatMessage } from "@/components/case-funnel-main";
import { StaffRolesPanel } from "@/components/staff-roles-panel";
import { humanizeStaffApiError } from "@/lib/staff-api-errors";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

type StaffRole = "operator" | "expert" | "admin";

type Me = {
  user_id: string;
  email: string | null;
  role: StaffRole | null;
  is_staff: boolean;
  role_capabilities?: {
    can_view_analytics?: boolean;
    can_manage_roles?: boolean;
    can_manage_finance?: boolean;
  };
};

type StaffCaseSummary = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  client_name: string | null;
  client_phone: string | null;
  expert_user_id: string | null;
  checklist_open_count: number;
  crm_external_id: string | null;
  crm_url: string | null;
  meeting_url?: string | null;
  preferred_channel: string;
  max_linked: boolean;
  web_linked: boolean;
  silent_days: number;
  package_codes: string[];
  finance_attention?: "awaiting_invoice" | "payable" | null;
  next_action?: string | null;
  next_action_at?: string | null;
  waiting_on?: string | null;
  priority?: string | null;
  deadline_status?: string | null;
  is_test?: boolean;
  last_event?: string | null;
};

type WorkQueueItem = {
  case_id: string;
  client_name: string | null;
  priority: "urgent" | "today" | "standard";
  pipeline_status: string;
  b2c_status: string;
  waiting_on: string;
  last_event: string;
  next_action: string;
  next_action_at: string | null;
  deadline_status: "overdue" | "soon" | "today" | "ok" | "waiting";
  channel: string;
  expert_user_id: string | null;
  doc_flags?: Record<string, boolean>;
};

type Dashboard = {
  new_leads: number;
  by_pipeline: Record<string, number>;
  by_b2c: Record<string, number>;
  payments_pending: number;
  payments_paid: number;
  silent: Record<string, number>;
  channel_conflicts: number;
  unlinked_max: number;
  unlinked_web: number;
  needs_reply: number;
  needs_reply_over_30m: number;
  deadline_today: number;
  waiting_docs: number;
  waiting_docs_max_days: number;
  sla_risk: number;
  greeting_priority_count: number;
  payments_pending_amount: number;
  payments_paid_today: number;
  payments_paid_today_amount: number;
  sla_control: Record<string, number>;
  doc_status: Record<string, number>;
  work_queue: WorkQueueItem[];
  my_tasks_today: WorkQueueItem[];
};

type RoleCapabilities = {
  can_edit_pipeline: boolean;
  can_edit_checklist: boolean;
  can_confirm_result: boolean;
  can_manage_orders: boolean;
  can_manage_roles: boolean;
  can_view_ocr: boolean;
  can_knowledge_feedback: boolean;
};

type StaffCaseDetail = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  client: {
    full_name?: string;
    phone?: string;
    email?: string;
    preferred_channel: string;
    max_linked: boolean;
    web_linked: boolean;
    max_user_id?: string | null;
  };
  documents: {
    id: string;
    storage_path: string;
    doc_type?: string | null;
    doc_type_label?: string | null;
    created_at?: string;
    filename?: string | null;
    inner_date?: string | null;
    inner_title?: string | null;
    content_preview?: string | null;
  }[];
  checklist_items: {
    id: string;
    title: string;
    status: string;
    owner: string;
    item_type?: string;
  }[];
  findings?: { type?: string; detail?: string }[];
  analysis_notes?: string | null;
  ocr_texts?: unknown[];
  ils_periods?: unknown[];
  labor_periods?: unknown[];
  draft?: { title?: string; body?: string } | null;
  channels: {
    cabinet_url: string;
    staff_cabinet_url?: string | null;
    max_reply_url?: string | null;
    max_ops_bot_url?: string | null;
  };
  representatives?: {
    user_id: string;
    email?: string | null;
    full_name?: string | null;
    created_at?: string | null;
  }[];
  crm_url?: string | null;
  meeting_url?: string | null;
  tracker_last_issue_key?: string | null;
  tracker_issue_url?: string | null;
  tracker_issues?: {
    id: string;
    tracker_issue_key: string;
    tracker_issue_url?: string | null;
    issue_type: string;
    is_open?: boolean;
    created_at?: string;
  }[];
  expert_user_id?: string | null;
  consent_accepted?: boolean;
  next_action?: string | null;
  next_action_at?: string | null;
  waiting_on?: string | null;
  is_test?: boolean;
  silent_days?: number;
  loss_reason?: string | null;
  closed_at?: string | null;
  role_capabilities: RoleCapabilities;
  audit: { id?: number; action: string; at: string; actor_id?: string }[];
  orders?: {
    id: string;
    package_code: string;
    amount_rub: number;
    status: string;
    finance_status?: string;
    pay_url?: string | null;
    qr_url?: string | null;
    sent_channel?: string | null;
    sent_at?: string | null;
    service_label?: string | null;
    invoice_number?: string | null;
  }[];
  orders_summary?: { package_code: string; status: string }[];
  result?: {
    evidence: Record<string, unknown> | null;
    success_fee: { sf_lump: number; sf_month: number; sf_total: number };
  } | null;
  warning: string;
};

type View = "dashboard" | "cases" | "case" | "finance" | "analytics" | "roles";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
const SITE_URL = "https://proverkastaza.ru";
const DEFAULT_MAX_OPS_BOT = "https://max.ru/id8905998693_3_bot";
const ADMIN_DEEP_LINK_KEY = "sfrfr_admin_deep_link";

type AdminDeepLink = { caseId: string; focusChat: boolean };

function captureAdminDeepLink(): AdminDeepLink | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const caseId = (params.get("case") || "").trim();
  const focusParam = (params.get("focus") || "").trim().toLowerCase();
  const focusChat =
    focusParam === "chat" ||
    focusParam === "max-reply" ||
    focusParam === "max_reply" ||
    window.location.hash === "#max-reply";
  if (caseId) {
    const link: AdminDeepLink = { caseId, focusChat };
    try {
      window.sessionStorage.setItem(ADMIN_DEEP_LINK_KEY, JSON.stringify(link));
    } catch {
      // private mode / quota
    }
    return link;
  }
  try {
    const raw = window.sessionStorage.getItem(ADMIN_DEEP_LINK_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AdminDeepLink;
    if (parsed?.caseId) return parsed;
  } catch {
    // ignore
  }
  return null;
}

function clearAdminDeepLink() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(ADMIN_DEEP_LINK_KEY);
  } catch {
    // ignore
  }
  try {
    const u = new URL(window.location.href);
    u.searchParams.delete("case");
    u.searchParams.delete("focus");
    if (u.hash === "#max-reply") u.hash = "";
    window.history.replaceState({}, "", `${u.pathname}${u.search}${u.hash}`);
  } catch {
    // ignore
  }
}

/** Экран входа: MAX (основной) | код на почту | заявка на доступ. */
type AuthScreen = "max" | "email_otp" | "register";

function chatUrlOnly(url: string): string {
  try {
    const u = new URL(url || DEFAULT_MAX_OPS_BOT);
    u.search = "";
    u.hash = "";
    return u.toString();
  } catch {
    return DEFAULT_MAX_OPS_BOT;
  }
}

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

function SiteReturnPanel() {
  return (
    <a className="auth-return-panel" href={SITE_URL}>
      <span className="auth-return-panel__title">Вернуться на сайт</span>
      <span className="auth-return-panel__hint">proverkastaza.ru</span>
    </a>
  );
}

const CHANNEL_LABELS: Record<string, string> = {
  max_miniapp: "MAX",
  web_cabinet: "Веб-кабинет",
  unset: "не выбран",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: "Срочно",
  today: "Сегодня",
  standard: "Стандартно",
};

const DOC_STATUS_LABELS: Record<string, string> = {
  consent_missing: "Нет согласия на ПДн",
  ils_missing: "Не получена выписка ИЛС",
  labor_missing: "Не получена трудовая",
  archive_needed: "Ожидаем архивную справку",
  discrepancy: "Расхождения ИЛС и трудовой",
  extra_info: "Нужна информация от клиента",
  project_ready: "Проект обращения готов",
  sfr_reply: "Ответ СФР — нужен разбор",
};

function formatRub(value: number): string {
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(value || 0))} ₽`;
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function apiFetch<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const raw = (await response.text()) || `HTTP ${response.status}`;
    let detail: string | Record<string, unknown> = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        detail = parsed.detail;
      } else if (parsed.detail && typeof parsed.detail === "object") {
        detail = parsed.detail as Record<string, unknown>;
      }
    } catch {
      /* оставить сырой текст */
    }
    const rawMessage =
      typeof detail === "string"
        ? detail
        : typeof detail.detail === "string"
          ? detail.detail
          : `HTTP ${response.status}`;
    const message = humanizeStaffApiError(rawMessage);
    const err = new Error(message) as Error & {
      status?: number;
      payload?: Record<string, unknown>;
    };
    err.status = response.status;
    if (typeof detail === "object") err.payload = detail;
    throw err;
  }
  return response.json() as Promise<T>;
}

async function publicFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const raw = (await response.text()) || `HTTP ${response.status}`;
    let message = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        message = parsed.detail;
      }
    } catch {
      /* оставить сырой текст */
    }
    throw new Error(humanizeStaffApiError(message));
  }
  return response.json() as Promise<T>;
}

export function AdminCabinet() {
  const supabase = useMemo(
    () => (supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null),
    [],
  );
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [registerConsent, setRegisterConsent] = useState(false);
  const [registerSent, setRegisterSent] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [authScreen, setAuthScreen] = useState<AuthScreen>("max");
  const [maxTicket, setMaxTicket] = useState("");
  const [maxPairCode, setMaxPairCode] = useState("");
  const [maxWaitStatus, setMaxWaitStatus] = useState("");
  const [maxBotUrl, setMaxBotUrl] = useState(DEFAULT_MAX_OPS_BOT);
  const [maxReplyBody, setMaxReplyBody] = useState("");
  const [marketingConsentLabel, setMarketingConsentLabel] = useState<string | null>(null);
  const [replySuggestions, setReplySuggestions] = useState<string[]>([]);
  const [stepHint, setStepHint] = useState<{
    action: string;
    reason: string;
    source: string;
  } | null>(null);
  const [stepMessages, setStepMessages] = useState<StepChatMessage[]>([]);
  const [maxReplyFocus, setMaxReplyFocus] = useState(false);
  const [composerFlash, setComposerFlash] = useState(false);
  const [dupDialog, setDupDialog] = useState<{
    code: string;
    lastAt?: string;
    preview?: string;
    count48h?: number;
  } | null>(null);
  const [sfrReceived, setSfrReceived] = useState(false);
  const [notice, setNotice] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<StaffCaseSummary[]>([]);
  const [detail, setDetail] = useState<StaffCaseDetail | null>(null);
  const [messages, setMessages] = useState<{ id: string; author_kind: string; body: string; created_at: string }[]>([]);
  const [finance, setFinance] = useState<FinanceSnapshot | null>(null);
  const [financeQueue, setFinanceQueue] = useState("all");
  const [financeQ, setFinanceQ] = useState("");
  const [financePeriod, setFinancePeriod] = useState("");
  const [financePackage, setFinancePackage] = useState("");
  const [financeIncludeTest, setFinanceIncludeTest] = useState(false);
  const [financeLoading, setFinanceLoading] = useState(false);
  const [createInvoiceOpen, setCreateInvoiceOpen] = useState(false);
  const [trackerModalOpen, setTrackerModalOpen] = useState(false);
  const [trackerIssueType, setTrackerIssueType] = useState("process_improvement");
  const [trackerPriority, setTrackerPriority] = useState("normal");
  const [trackerDirection, setTrackerDirection] = useState("ops");
  const [trackerRepeat, setTrackerRepeat] = useState("once");
  const [trackerDesc, setTrackerDesc] = useState("");
  const [trackerTitle, setTrackerTitle] = useState("");
  const [trackerForceNew, setTrackerForceNew] = useState(false);
  const [invoiceCaseId, setInvoiceCaseId] = useState("");
  const [invoiceCode, setInvoiceCode] = useState<"DIAG" | "ACCOMP">("DIAG");
  const [invoiceLabel, setInvoiceLabel] = useState("Диагностика");
  const [invoiceAmount, setInvoiceAmount] = useState("3000");
  const [invoiceDue, setInvoiceDue] = useState("");
  const [markPaidOrder, setMarkPaidOrder] = useState<FinanceOrder | null>(null);
  const [paidAt, setPaidAt] = useState("");
  const [paidAmount, setPaidAmount] = useState("");
  const [paidMethod, setPaidMethod] = useState("transfer");
  const [paidRef, setPaidRef] = useState("");
  const [cancelOrder, setCancelOrder] = useState<FinanceOrder | null>(null);
  const [cancelReason, setCancelReason] = useState("refusal");
  const [cancelComment, setCancelComment] = useState("");
  const [analytics, setAnalytics] = useState<AnalyticsSnapshot | null>(null);
  const [analyticsFilters, setAnalyticsFilters] = useState({
    period: "30d",
    dateFrom: "",
    dateTo: "",
    channel: "",
    packageCode: "",
    pipelineStatus: "",
  });
  const [busy, setBusy] = useState(false);

  const [q, setQ] = useState("");
  const [filterPipeline, setFilterPipeline] = useState("");
  const [filterChannel, setFilterChannel] = useState("");
  const [filterPackage, setFilterPackage] = useState("");
  const [queueFilter, setQueueFilter] = useState("all");
  const [registryQueue, setRegistryQueue] = useState("active");
  const [casesLoading, setCasesLoading] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [nextActionText, setNextActionText] = useState("");
  const [nextActionAt, setNextActionAt] = useState("");
  const [waitingOn, setWaitingOn] = useState("staff");

  const [checklistTitle, setChecklistTitle] = useState("");
  const [pipelineStatus, setPipelineStatus] = useState("human_review");
  const [beforeRub, setBeforeRub] = useState("");
  const [afterRub, setAfterRub] = useState("");
  const [lumpRub, setLumpRub] = useState("");
  const [feedbackQuality, setFeedbackQuality] = useState("verified");
  const [feedbackText, setFeedbackText] = useState("");
  const [orderAmount, setOrderAmount] = useState("");
  const [repEmail, setRepEmail] = useState("");
  const [orderCode, setOrderCode] = useState<"DIAG" | "ACCOMP" | "SF_LUMP" | "SF_MONTH">("DIAG");

  const token = session?.access_token;

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  const loadMe = useCallback(async () => {
    if (!token) return;
    const profile = await apiFetch<Me>("/api/portal/me", token);
    setMe(profile);
    if (!profile.is_staff) {
      setNotice("Нет доступа: требуется роль оператора, эксперта или администратора.");
    }
  }, [token]);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setDashboard(await apiFetch<Dashboard>("/api/portal/admin/dashboard", token));
  }, [token]);

  const loadCases = useCallback(
    async (overrides?: {
      queue?: string;
      preferred_channel?: string;
      pipeline_status?: string;
    }) => {
    if (!token) return;
      setCasesLoading(true);
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
      const pipeline = overrides?.pipeline_status ?? filterPipeline;
      const channel = overrides?.preferred_channel ?? filterChannel;
      const queue = overrides?.queue ?? registryQueue;
      if (pipeline) params.set("pipeline_status", pipeline);
      if (channel) params.set("preferred_channel", channel);
    if (filterPackage) params.set("package_code", filterPackage);
      params.set("queue", queue);
    const qs = params.toString();
      try {
    setCases(
      await apiFetch<StaffCaseSummary[]>(
        `/api/portal/admin/cases${qs ? `?${qs}` : ""}`,
        token,
      ),
    );
      } finally {
        setCasesLoading(false);
      }
    },
    [token, q, filterPipeline, filterChannel, filterPackage, registryQueue],
  );

  useEffect(() => {
    if (!token) return;
    void (async () => {
      try {
        await loadMe();
        await loadDashboard();
        await loadCases();
      } catch {
        setNotice("Нет доступа или API недоступен.");
      }
    })();
  }, [token, loadMe, loadDashboard, loadCases]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false },
    });
    if (error) {
      const msg =
        error.message?.toLowerCase().includes("signups not allowed") ||
        error.message?.toLowerCase().includes("user not found")
          ? "Почта не зарегистрирована для входа. Попросите администратора выдать роль (staff-grant) или войдите через MAX."
          : `Не удалось отправить код: ${error.message}`;
      setNotice(msg);
      return;
    }
    setOtpSent(true);
    setNotice("Код отправлен на рабочий email.");
  }

  async function requestMaxLogin(): Promise<boolean> {
    if (!apiBase) {
      setNotice("API не настроен.");
      return false;
    }
    if (!email.trim() || !email.includes("@")) {
      setNotice("Укажите рабочий email — роль должна быть уже выдана администратором.");
      return false;
    }
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/portal/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audience: "staff", email: email.trim().toLowerCase() }),
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
        throw new Error(
          typeof body.detail === "string" ? body.detail : "Не удалось начать вход через MAX.",
        );
      }
      setMaxTicket(body.ticket || "");
      setMaxPairCode(body.pair_code || "");
      setMaxWaitStatus(body.status || "pending_pair");
      if (body.max_bot_url) setMaxBotUrl(body.max_bot_url);
      setOtpSent(true);
      setNotice(
        body.message ||
          "Код появился ниже. Нажмите «Перейти в MAX», отправьте код в ops-бот и подтвердите вход.",
      );
      return true;
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось начать вход через MAX.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function getMaxLoginCode() {
    if (!email.trim() || !email.includes("@")) {
      setNotice("Сначала укажите рабочий email.");
      return;
    }
    await requestMaxLogin();
    }

  function openMaxChat() {
    window.open(chatUrlOnly(maxBotUrl), "_blank", "noopener,noreferrer");
  }

  function resetMaxWizard() {
    setOtpSent(false);
    setMaxTicket("");
    setMaxPairCode("");
    setMaxWaitStatus("");
    setNotice("");
  }

  function goAuthScreen(next: AuthScreen) {
    setAuthScreen(next);
    setOtpSent(false);
    setOtpCode("");
    setRegisterSent(false);
    setNotice("");
    if (next === "max") resetMaxWizard();
  }

  async function requestStaffRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!registerConsent) {
      setNotice("Отметьте согласие с СОПД — без него заявку отправить нельзя.");
      return;
    }
    if (!fullName.trim()) {
      setNotice("Укажите имя и фамилию.");
      return;
    }
    if (!email.trim() || !email.includes("@")) {
      setNotice("Укажите рабочий e-mail.");
      return;
    }
    if (!apiBase) {
      setNotice("API кабинета не настроен.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const result = await publicFetch<{ ok?: boolean; message?: string }>(
        "/api/public/staff-register",
        {
          method: "POST",
          body: JSON.stringify({
            email: email.trim(),
            display_name: fullName.trim(),
            consent: true,
          }),
        },
      );
      setRegisterSent(true);
      setNotice(
        result.message ||
          "Заявка отправлена. После подтверждения администратором на proverkastaza@yandex.ru вы получите письмо с доступом.",
      );
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Не удалось отправить заявку.");
    } finally {
      setBusy(false);
    }
  }

  // ПК ждёт: код в MAX → (при первом входе) руководитель → сессия
  useEffect(() => {
    if (!supabase || !apiBase || !maxTicket || session || authScreen !== "max" || !otpSent) {
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
  }, [supabase, apiBase, maxTicket, session, authScreen, otpSent]);

  async function verifyOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    const { error } = await supabase.auth.verifyOtp({
      email,
      token: otpCode,
      type: "email",
    });
    setNotice(error ? "Неверный код." : "");
  }

  async function openCase(caseId: string, opts?: { focusMaxReply?: boolean }): Promise<boolean> {
    if (!token) return false;
    if (opts?.focusMaxReply) {
      setMaxReplyFocus(true);
    }
    setBusy(true);
    try {
      const caseDetail = await apiFetch<StaffCaseDetail>(
        `/api/portal/admin/cases/${caseId}`,
        token,
      );
      let caseMessages: { id: string; author_kind: string; body: string; created_at: string }[] =
        [];
      try {
        caseMessages = await apiFetch<typeof caseMessages>(
          `/api/portal/cases/${caseId}/messages`,
          token,
        );
      } catch {
        // Карточка дела важнее — переписка может быть пустой на intake.
      }
      setDetail(caseDetail);
      setMessages(caseMessages);
      setPipelineStatus(caseDetail.pipeline_status);
      setNextActionText(caseDetail.next_action ?? "");
      setNextActionAt(caseDetail.next_action_at ? caseDetail.next_action_at.slice(0, 16) : "");
      setWaitingOn(caseDetail.waiting_on ?? "staff");
      setSfrReceived(
        ["result_confirmed", "success_fee_due", "success_fee_paid", "closed"].includes(
          caseDetail.b2c_status,
        ),
      );
      setLumpRub("");
      setDupDialog(null);
      setView("case");
      void loadMarketingConsent(caseId);
      return true;
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setNotice(
        detail.includes("case not found") || detail.includes("404")
          ? "Дело не найдено или недоступно для вашей роли."
          : `Не удалось открыть дело: ${detail || "ошибка API"}`,
      );
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    // Сохранить deep-link до логина (MAX часто открывает URL на экране входа).
    captureAdminDeepLink();
  }, []);

  useEffect(() => {
    if (!token || !me?.is_staff) return;
    const link = captureAdminDeepLink();
    if (!link?.caseId) return;
    let cancelled = false;
    void (async () => {
      // Deep-link из ops «клиент ждёт» / документ в чат → дело + чат.
      const ok = await openCase(link.caseId, { focusMaxReply: true });
      if (ok && !cancelled) clearAdminDeepLink();
    })();
    return () => {
      cancelled = true;
    };
    // openCase замыкается на token/state — достаточно staff-сессии.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, me?.is_staff]);

  useEffect(() => {
    if (view !== "case" || !detail || !maxReplyFocus) return;
    window.requestAnimationFrame(() => {
      document.getElementById("max-reply-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
      document.getElementById("max-reply-text")?.focus();
      setMaxReplyFocus(false);
    });
  }, [view, detail, maxReplyFocus]);

  useEffect(() => {
    if (view !== "case" || !detail || !token) return;
    const caseId = detail.id;
    const timer = window.setInterval(() => {
      void apiFetch<typeof messages>(`/api/portal/cases/${caseId}/messages`, token)
        .then((next) => {
          setMessages((prev) => {
            if (
              prev.length === next.length &&
              prev.every(
                (m, i) =>
                  m.id === next[i]?.id &&
                  m.body === next[i]?.body &&
                  m.created_at === next[i]?.created_at &&
                  m.author_kind === next[i]?.author_kind,
              )
            ) {
              return prev;
            }
            return next;
          });
        })
        .catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [view, detail?.id, token]);

  async function loadFinance(opts?: string | { queue?: string; q?: string; caseId?: string }) {
    if (!token) return;
    const normalized =
      typeof opts === "string" || opts === undefined
        ? { queue: opts ?? financeQueue }
        : opts;
    const nextQueue = normalized.queue ?? financeQueue;
    const nextQ =
      normalized.caseId?.trim() ||
      (normalized.q !== undefined ? normalized.q : financeQ);
    setFinanceQueue(nextQueue);
    if (normalized.caseId || normalized.q !== undefined) {
      setFinanceQ(nextQ);
    }
    setFinanceLoading(true);
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (nextQueue && nextQueue !== "all") params.set("queue", nextQueue);
      const qValue = String(nextQ || "").trim();
      if (qValue) params.set("q", qValue);
      if (financePeriod) params.set("period", financePeriod);
      if (financePackage) params.set("package_code", financePackage);
      if (financeIncludeTest) params.set("include_test", "true");
      const qs = params.toString();
      setFinance(await apiFetch(`/api/portal/admin/finance${qs ? `?${qs}` : ""}`, token));
      setView("finance");
      if (cases.length === 0) await loadCases();
    } catch {
      setNotice("Финансы недоступны для роли оператора.");
    } finally {
      setFinanceLoading(false);
      setBusy(false);
    }
  }

  async function loadAnalytics(nextFilters = analyticsFilters) {
    if (!token) return;
    setBusy(true);
    try {
      const params = new URLSearchParams();
      params.set("period", nextFilters.period);
      if (nextFilters.period === "custom") {
        if (nextFilters.dateFrom) params.set("date_from", nextFilters.dateFrom);
        if (nextFilters.dateTo) params.set("date_to", nextFilters.dateTo);
      }
      if (nextFilters.channel) params.set("channel", nextFilters.channel);
      if (nextFilters.packageCode) params.set("package_code", nextFilters.packageCode);
      if (nextFilters.pipelineStatus) params.set("pipeline_status", nextFilters.pipelineStatus);
      setAnalytics(
        await apiFetch<AnalyticsSnapshot>(
          `/api/portal/admin/analytics?${params.toString()}`,
          token,
        ),
      );
      setView("analytics");
    } catch (error) {
      const hint = error instanceof Error ? error.message : "";
      setNotice(
        hint && !/operator/i.test(hint)
          ? `Аналитика недоступна: ${hint}`
          : "Аналитика недоступна. Для администратора и специалиста раздел должен открываться.",
      );
    } finally {
      setBusy(false);
    }
  }

  function openRegistryFromAnalytics(filter: Partial<Record<"queue" | "preferred_channel" | "pipeline_status", string>>) {
    if (filter.queue) setRegistryQueue(filter.queue);
    if (filter.preferred_channel !== undefined) setFilterChannel(filter.preferred_channel);
    if (filter.pipeline_status) setFilterPipeline(filter.pipeline_status);
    setView("cases");
    void loadCases({
      queue: filter.queue,
      preferred_channel: filter.preferred_channel,
      pipeline_status: filter.pipeline_status,
    });
  }

  async function loadRoles() {
    if (!token) return;
      setView("roles");
  }

  async function requestReview() {
    if (!token || !detail) return;
    await apiFetch(`/api/portal/admin/cases/${detail.id}/request-review`, token, { method: "POST" });
    setNotice("Проверка запрошена.");
    await openCase(detail.id);
  }

  async function createTelemost() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      const result = await apiFetch<{
        ok?: boolean;
        skipped?: boolean;
        join_url?: string;
        error?: string;
        hint?: string;
        detail?: unknown;
      }>(`/api/portal/admin/cases/${detail.id}/telemost`, token, { method: "POST" });
      if (result.ok && result.join_url) {
        setNotice(`Телемост создан: ${result.join_url}`);
        await openCase(detail.id);
      } else if (result.skipped) {
        setNotice("Телемост пропущен (нет токена / выключен).");
      } else {
        setNotice(
          `Телемост: ${result.error || "ошибка"}${result.hint ? ` — ${result.hint}` : ""}`,
        );
      }
    } catch {
      setNotice("Не удалось создать Телемост.");
    } finally {
      setBusy(false);
    }
  }

  async function createTrackerIssue() {
    if (!token || !detail) return;
    if (trackerDesc.trim().length < 10) {
      setNotice("Описание задачи: минимум 10 символов (без ПДн).");
      return;
    }
    setBusy(true);
    try {
      const result = await apiFetch<{
        ok?: boolean;
        duplicate?: boolean;
        tracker_issue_key?: string;
        tracker_issue_url?: string;
        message?: string;
        detail?: { error?: string; fields?: string[] } | string;
      }>(`/api/portal/admin/cases/${detail.id}/tracker`, token, {
        method: "POST",
        body: JSON.stringify({
          issue_type: trackerIssueType,
          priority: trackerPriority,
          direction: trackerDirection,
          source: "cabinet",
          description: trackerDesc.trim(),
          title_hint: trackerTitle.trim() || null,
          funnel_stage: detail.pipeline_status,
          channel:
            detail.client.preferred_channel === "max_miniapp"
              ? "max"
              : detail.client.preferred_channel === "web_cabinet"
                ? "web"
                : "unknown",
          repeatability: trackerRepeat,
          force_new: trackerForceNew,
        }),
      });
      if (result.ok && result.tracker_issue_key) {
        const msg = result.duplicate
          ? `Уже есть открытая задача: ${result.tracker_issue_key}`
          : `Создано в Tracker: ${result.tracker_issue_key}`;
        setNotice(msg);
        setTrackerModalOpen(false);
        setTrackerDesc("");
        setTrackerTitle("");
        setTrackerForceNew(false);
        await openCase(detail.id);
      } else {
        const d = result.detail;
        const fields =
          d && typeof d === "object" && Array.isArray(d.fields) ? d.fields.join(", ") : "";
        setNotice(
          `Tracker: ${(d && typeof d === "object" && d.error) || "ошибка"}${
            fields ? ` (${fields})` : ""
          }`,
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "не удалось создать";
      setNotice(`Tracker: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function sendWorkspaceEmail() {
    if (!token || !detail) return;
    if (!detail.client.email) {
      setNotice("У клиента нет email — письмо не отправить.");
      return;
    }
    setBusy(true);
    try {
      const result = await apiFetch<{ ok?: boolean; skipped?: boolean; error?: string }>(
        `/api/portal/admin/cases/${detail.id}/email`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ template: "request_docs" }),
        },
      );
      if (result.ok) setNotice("Письмо «запрос документов» отправлено.");
      else if (result.skipped) setNotice("Почта пропущена (нет токена / выключена).");
      else setNotice(`Почта: ${result.error || "ошибка"}`);
    } catch {
      setNotice("Не удалось отправить письмо.");
    } finally {
      setBusy(false);
    }
  }

  async function takeCase(caseId: string) {
    if (!token || !me) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${caseId}/assign-expert`, token, {
        method: "PATCH",
        body: JSON.stringify({ expert_user_id: me.user_id }),
      });
      setNotice("Дело взято в работу.");
      await loadCases();
    } catch {
      setNotice("Не удалось взять дело в работу.");
    } finally {
      setBusy(false);
    }
  }

  async function suggestStep(caseId: string) {
    if (!token) return;
    setBusy(true);
    setNotice("DeepSeek думает над следующим шагом…");
    setStepHint(null);
    setStepMessages([]);
    try {
      const hint = await apiFetch<{
        next_action: string;
        waiting_on: string;
        reason?: string;
        source?: string;
        chat_messages?: Array<string | { kind?: string; text?: string }>;
      }>(`/api/portal/admin/cases/${caseId}/suggest-next-action`, token, { method: "POST" });
      // Сохраняем шаг в деле, но НЕ отправляем текст клиенту.
      await apiFetch(`/api/portal/admin/cases/${caseId}/next-action`, token, {
        method: "PATCH",
        body: JSON.stringify({ next_action: hint.next_action, waiting_on: hint.waiting_on }),
      });
      if (!detail || detail.id === caseId) {
        setNextActionText(hint.next_action);
        if (hint.waiting_on) setWaitingOn(hint.waiting_on);
        if (detail?.id === caseId) {
          setDetail({
            ...detail,
            next_action: hint.next_action,
            waiting_on: hint.waiting_on,
          });
        }
      }
      const kinds: StepChatMessage["kind"][] = ["full", "short", "cabinet_howto"];
      const msgs: StepChatMessage[] = [];
      for (const [idx, item] of (hint.chat_messages || []).entries()) {
        if (typeof item === "string" && item.trim()) {
          msgs.push({ kind: kinds[idx] || "full", text: item.trim() });
        } else if (item && typeof item === "object" && String(item.text || "").trim()) {
          const k = String(item.kind || kinds[idx] || "full");
          const kind = (kinds.includes(k as StepChatMessage["kind"])
            ? k
            : kinds[idx] || "full") as StepChatMessage["kind"];
          msgs.push({ kind, text: String(item.text).trim() });
        }
      }
      setStepHint({
        action: hint.next_action,
        reason: (hint.reason || "").trim(),
        source: hint.source || "heuristic",
      });
      setStepMessages(msgs);
      setNotice(
        "Подсказка готова: выберите тип сообщения и нажмите подстановку, затем отправьте в MAX вручную.",
      );
      if (view !== "case") {
        await loadCases();
        await loadDashboard();
      }
    } catch (error) {
      setNotice(
        error instanceof Error
          ? `Не удалось получить подсказку шага: ${error.message}`
          : "Не удалось получить подсказку шага.",
      );
    } finally {
      setBusy(false);
    }
  }

  function applyStepMessageToChat(text: string, opts?: { confirmAssign?: boolean }) {
    if (opts?.confirmAssign && detail && !detail.expert_user_id) {
      if (!window.confirm("Назначить себе и подставить текст в чат?")) return;
      void takeCase(detail.id);
    }
    setMaxReplyBody(text);
    setReplySuggestions([]);
    setMaxReplyFocus(true);
    setComposerFlash(true);
    window.setTimeout(() => setComposerFlash(false), 2000);
    setNotice("Текст добавлен в черновик. Отправьте после проверки.");
  }

  async function recordServiceConsent() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/service-consent`, token, {
        method: "POST",
      });
      setNotice("Согласие клиента на услугу зафиксировано.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось зафиксировать согласие.");
    } finally {
      setBusy(false);
    }
  }

  async function loadMarketingConsent(caseId: string) {
    if (!token) return;
    try {
      const data = await apiFetch<{
        ok?: boolean;
        channels?: Record<string, { status?: string }>;
      }>(`/api/portal/admin/cases/${caseId}/marketing-consent`, token);
      const st = data.channels?.max?.status || "none";
      const map: Record<string, string> = {
        granted: "есть согласие",
        denied: "отказ",
        revoked: "отозвано",
        none: "нет согласия",
      };
      setMarketingConsentLabel(map[st] || st);
    } catch {
      setMarketingConsentLabel("недоступно");
    }
  }

  async function requestMarketingConsent() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/marketing-consent/request`, token, {
        method: "POST",
      });
      setNotice("Запрос согласия на рассылку отправлен в MAX.");
      await loadMarketingConsent(detail.id);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Не удалось запросить согласие на рассылку.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function requestDocsFor(caseId: string) {
    if (!token) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ ok?: boolean; skipped?: boolean; error?: string }>(
        `/api/portal/admin/cases/${caseId}/email`,
        token,
        { method: "POST", body: JSON.stringify({ template: "request_docs" }) },
      );
      if (result.ok) setNotice("Письмо «запрос документов» отправлено.");
      else if (result.skipped) setNotice("Почта пропущена (нет токена / выключена).");
      else setNotice(`Почта: ${result.error || "ошибка"}`);
    } catch {
      setNotice("Не удалось отправить запрос документов.");
    } finally {
      setBusy(false);
    }
  }

  async function markTest(caseId: string, isTest: boolean) {
    if (!token) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${caseId}/flags`, token, {
        method: "PATCH",
        body: JSON.stringify({ is_test: isTest }),
      });
      setNotice(isTest ? "Помечено как тестовое." : "Убрано из тестовых.");
      await loadCases();
    } catch {
      setNotice("Не удалось обновить флаг. Нужна роль администратора и миграция is_test.");
    } finally {
      setBusy(false);
    }
  }

  async function saveNextAction() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/next-action`, token, {
        method: "PATCH",
        body: JSON.stringify({
          next_action: nextActionText.trim() || null,
          next_action_at: nextActionAt ? new Date(nextActionAt).toISOString() : null,
          waiting_on: waitingOn,
        }),
      });
      setNotice("Следующий шаг сохранён.");
      await openCase(detail.id);
      await loadDashboard();
    } catch {
      setNotice("Не удалось сохранить следующий шаг. Если колонки ещё не применены в БД — примените миграцию.");
    } finally {
      setBusy(false);
    }
  }

  async function saveArchivePrep(payload: {
    archive_prep_status: string | null;
    archive_tariff: string | null;
    archive_successor: string | null;
    archive_target: string | null;
    archive_followup_at: string | null;
  }) {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/archive-prep`, token, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setNotice("Архивный блок сохранён.");
      await openCase(detail.id);
    } catch {
      setNotice("Не удалось сохранить архивный блок. Нужна миграция cases_archive_prep.");
    } finally {
      setBusy(false);
    }
  }

  async function closeCase(payload: {
    outcome: "success" | "lost";
    loss_reason?: string;
  }) {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/close`, token, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setNotice(
        payload.outcome === "lost"
          ? `Отказ зафиксирован: ${payload.loss_reason || "—"}`
          : "Дело закрыто успешно.",
      );
      await openCase(detail.id);
      await loadDashboard();
      await loadCases();
    } catch {
      setNotice(
        "Не удалось закрыть дело. Проверьте причину отказа или примените миграцию loss_reason.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function savePipeline() {
    if (!token || !detail) return;
    await apiFetch(`/api/portal/admin/cases/${detail.id}/pipeline-status`, token, {
      method: "PATCH",
      body: JSON.stringify({ pipeline_status: pipelineStatus }),
    });
    setNotice("Этап обновлён.");
    await openCase(detail.id);
  }

  async function addChecklist(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail || !checklistTitle.trim()) return;
    await apiFetch(`/api/portal/admin/cases/${detail.id}/checklist`, token, {
      method: "POST",
      body: JSON.stringify({ title: checklistTitle.trim(), owner: "client", item_type: "action" }),
    });
    setChecklistTitle("");
    await openCase(detail.id);
  }

  async function toggleChecklist(itemId: string, status: string) {
    if (!token || !detail) return;
    await apiFetch(`/api/portal/admin/cases/${detail.id}/checklist/${itemId}`, token, {
      method: "PATCH",
      body: JSON.stringify({ status: status === "done" ? "open" : "done" }),
    });
    await openCase(detail.id);
  }

  async function confirmResult(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail) return;
    await apiFetch(`/api/portal/admin/cases/${detail.id}/result/confirm`, token, {
      method: "POST",
      body: JSON.stringify({
        monthly_before_rub: Number(beforeRub),
        monthly_after_rub: Number(afterRub),
        lump_sum_rub: Number(lumpRub || 0),
      }),
    });
    setNotice("Результат подтверждён, запись в audit.");
    await openCase(detail.id);
  }

  async function createOrder(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail) return;
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/orders`, token, {
        method: "POST",
        body: JSON.stringify({
          package_code: orderCode,
          amount_rub: Number(orderAmount),
        }),
      });
      setNotice("Счёт создан.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось создать счёт.");
    }
  }

  async function createFinanceInvoice(event: FormEvent) {
    event.preventDefault();
    if (!token || !invoiceCaseId) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${invoiceCaseId}/orders`, token, {
        method: "POST",
        body: JSON.stringify({
          package_code: invoiceCode,
          amount_rub: Number(invoiceAmount),
          status: "draft",
          service_label: invoiceLabel,
          due_at: invoiceDue ? new Date(invoiceDue).toISOString() : undefined,
        }),
      });
      setCreateInvoiceOpen(false);
      setNotice("Черновик счёта создан.");
      await loadFinance(financeQueue);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось создать счёт.");
    } finally {
      setBusy(false);
    }
  }

  async function copyPayLink(order: FinanceOrder) {
    if (!token) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ pay_url?: string }>(
        `/api/portal/admin/orders/${order.id}/pay-link`,
        token,
        { method: "POST", body: JSON.stringify({ send_max: false }) },
      );
      const url = result.pay_url || "";
      if (!url) throw new Error("Нет ссылки");
      await navigator.clipboard.writeText(url);
      setNotice("Короткая ссылка ЮKassa скопирована. QR — в карточке счёта.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("Не удалось получить ссылку на оплату.");
    } finally {
      setBusy(false);
    }
  }

  async function sendPayLink(order: FinanceOrder) {
    if (!token) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ sent?: boolean; pay_url?: string }>(
        `/api/portal/admin/orders/${order.id}/pay-link`,
        token,
        { method: "POST", body: JSON.stringify({ send_max: true }) },
      );
      setNotice(result.sent ? "Ссылка и QR отправлены клиенту в MAX." : "Ссылка создана, MAX не отправлен.");
      await loadFinance(financeQueue);
      if (detail && String(order.case_id) === detail.id) {
        await openCase(detail.id);
        const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
        setMessages(next);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось отправить ссылку в MAX.");
    } finally {
      setBusy(false);
    }
  }

  async function sendPayLinkForCaseOrder(orderId: string) {
    if (!token || !detail) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ sent?: boolean }>(
        `/api/portal/admin/orders/${orderId}/pay-link`,
        token,
        { method: "POST", body: JSON.stringify({ send_max: true }) },
      );
      setNotice(
        result.sent
          ? "Счёт отправлен в MAX — текст, кнопка и QR появятся в ленте чата."
          : "Ссылка создана, но MAX не отправлен (проверьте привязку клиента).",
      );
      await openCase(detail.id);
      const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
      setMessages(next);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось отправить счёт в MAX.");
    } finally {
      setBusy(false);
    }
  }

  async function copyPayLinkForCaseOrder(orderId: string) {
    if (!token || !detail) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ pay_url?: string }>(
        `/api/portal/admin/orders/${orderId}/pay-link`,
        token,
        { method: "POST", body: JSON.stringify({ send_max: false }) },
      );
      const url = result.pay_url || "";
      if (!url) throw new Error("Нет ссылки");
      await navigator.clipboard.writeText(url);
      setNotice("Ссылка скопирована. QR появится в блоке оплаты дела.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось получить ссылку.");
    } finally {
      setBusy(false);
    }
  }

  async function remindPayment(order: FinanceOrder, sendMax: boolean) {
    if (!token) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ reminder_draft?: string; sent?: boolean }>(
        `/api/portal/admin/orders/${order.id}/remind`,
        token,
        { method: "POST", body: JSON.stringify({ send_max: sendMax, channel: sendMax ? "max" : "web" }) },
      );
      setNotice(result.sent ? "Напоминание отправлено в MAX." : "Черновик напоминания сохранён.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("Не удалось подготовить напоминание.");
    } finally {
      setBusy(false);
    }
  }

  async function submitMarkPaid(event: FormEvent) {
    event.preventDefault();
    if (!token || !markPaidOrder) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/orders/${markPaidOrder.id}/mark-paid`, token, {
        method: "POST",
        body: JSON.stringify({
          paid_at: paidAt ? new Date(paidAt).toISOString() : new Date().toISOString(),
          amount_rub: Number(paidAmount),
          method: paidMethod,
          reference: paidRef.trim(),
        }),
      });
      setMarkPaidOrder(null);
      setNotice("Оплата отмечена, запись в журнале аудита.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("Не удалось отметить оплату.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCancel(event: FormEvent) {
    event.preventDefault();
    if (!token || !cancelOrder) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/orders/${cancelOrder.id}/cancel`, token, {
        method: "POST",
        body: JSON.stringify({ reason: cancelReason, comment: cancelComment.trim() || null }),
      });
      setCancelOrder(null);
      setNotice("Счёт отменён.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("Не удалось отменить счёт.");
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail) return;
    await apiFetch(`/api/portal/admin/cases/${detail.id}/knowledge-feedback`, token, {
      method: "POST",
      body: JSON.stringify({
        what_worked: feedbackText,
        quality: feedbackQuality,
        sfr_outcome: "unknown",
      }),
    });
    setFeedbackText("");
    setNotice(`Обратная связь для базы знаний сохранена (${labelFeedbackQuality(feedbackQuality)}).`);
  }

  function focusMaxReplyPanel() {
    setMaxReplyFocus(true);
  }

  async function suggestReplies() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      const result = await apiFetch<{ suggestions?: string[] }>(
        `/api/portal/admin/cases/${detail.id}/suggest-replies`,
        token,
        { method: "POST" },
      );
      setReplySuggestions(result.suggestions ?? []);
      if (!(result.suggestions && result.suggestions.length)) {
        setNotice("DeepSeek не вернул варианты — проверьте ключ Yandex AI Studio.");
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось получить подсказки.");
    } finally {
      setBusy(false);
    }
  }

  async function sendMaxReply(opts?: { force?: boolean }) {
    if (!token || !detail || !maxReplyBody.trim() || !detail.client.max_linked) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/max-reply`, token, {
        method: "POST",
        body: JSON.stringify({ message: maxReplyBody.trim(), force: Boolean(opts?.force) }),
      });
      setMaxReplyBody("");
      setDupDialog(null);
      setNotice("Сообщение отправлено клиенту в MAX.");
      const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
      setMessages(next);
    } catch (error) {
      const err = error as Error & { status?: number; payload?: Record<string, unknown> };
      if (err.status === 409 && err.payload && !opts?.force) {
        const code = String(err.payload.code || "duplicate_message");
        const count48h = Number(err.payload.count_48h || 0);
        setDupDialog({
          code,
          lastAt: typeof err.payload.last_at === "string" ? err.payload.last_at : undefined,
          preview:
            typeof err.payload.last_body_preview === "string"
              ? err.payload.last_body_preview
              : undefined,
          count48h,
        });
        return;
      }
      setNotice(error instanceof Error ? error.message : "Не удалось отправить в MAX.");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage() {
    if (!token || !detail || !maxReplyBody.trim()) return;
    setBusy(true);
    try {
    await apiFetch(`/api/portal/cases/${detail.id}/messages`, token, {
      method: "POST",
        body: JSON.stringify({ body: maxReplyBody.trim() }),
    });
      setMaxReplyBody("");
    const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
    setMessages(next);
      setNotice("Сообщение сохранено в ленту дела.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось сохранить сообщение.");
    } finally {
      setBusy(false);
    }
  }

  async function addRepresentative(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail || !repEmail.trim()) return;
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/representatives`, token, {
        method: "POST",
        body: JSON.stringify({ email: repEmail.trim() }),
      });
      setRepEmail("");
      setNotice("Представитель добавлен.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось добавить представителя.");
    }
  }

  async function removeRepresentative(userId: string) {
    if (!token || !detail) return;
    try {
      await apiFetch(
        `/api/portal/admin/cases/${detail.id}/representatives/${userId}`,
        token,
        { method: "DELETE" },
      );
      setNotice("Доступ представителя снят.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось снять доступ.");
    }
  }

  async function openSigned(docId: string) {
    if (!token || !detail) return;
    const signed = await apiFetch<{ url: string; expires_in: number }>(
      `/api/portal/cases/${detail.id}/documents/${docId}/signed-url`,
      token,
      { method: "POST" },
    );
    window.open(signed.url, "_blank", "noopener,noreferrer");
    setNotice(`Signed URL: ${signed.expires_in} сек.`);
  }

  async function uploadDiagnosisReport(file: File) {
    if (!token || !detail) return;
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setNotice("Нужен PDF результата диагностики.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("doc_type", "diagnosis_report");
      await apiFetch(`/api/portal/cases/${detail.id}/documents`, token, {
        method: "POST",
        body: form,
      });
      setNotice("PDF результата диагностики загружен в кабинет.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось загрузить PDF.");
    } finally {
      setBusy(false);
    }
  }

  async function publishDiagnosis(documentId: string) {
    if (!token || !detail) return;
    setBusy(true);
    try {
      const out = await apiFetch<{
        share_url_once?: string;
        jobs?: { id: string; job_type: string; channel: string; status: string }[];
      }>(`/api/portal/admin/cases/${detail.id}/diagnosis/publish`, token, {
        method: "POST",
        body: JSON.stringify({ document_id: documentId, channels: ["email", "max"] }),
      });
      const n = out.jobs?.length ?? 0;
      let msg = `Опубликовано. Черновиков уведомлений: ${n}.`;
      if (out.share_url_once) {
        try {
          await navigator.clipboard.writeText(out.share_url_once);
          msg += " Ссылка скопирована в буфер (один раз).";
        } catch {
          msg += " Ссылка в ответе API (один раз).";
        }
      }
      setNotice(msg);
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось опубликовать.");
    } finally {
      setBusy(false);
    }
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
              Проверка стажа · сотрудники
            </BrandHomeLink>
          </p>
          <h1>Кабинет сотрудника</h1>

          <div className="auth-tabs" role="tablist" aria-label="Вход или заявка на доступ">
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
              Запрос доступа
            </button>
          </div>

          {authScreen === "max" ? (
            <>
              <p className="lead lead-compact">
                Вход через ops-бот MAX «Проверка стажа-Ops»: получите код на этой странице,
                подтвердите в MAX. Доступ открывается после одобрения администратором.
              </p>
              <label htmlFor="email-max">Рабочий email</label>
              <input
                id="email-max"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={otpSent && Boolean(maxTicket)}
                placeholder="name@company.ru"
              />
              <div className="max-wizard max-wizard--actions">
                {!otpSent ? (
                  <>
                    <button
                      type="button"
                      className="max-action-btn"
                      disabled={busy}
                      onClick={() => void getMaxLoginCode()}
                    >
                      Получить код
                    </button>
                    <ol className="max-login-steps">
                      <li>Нажмите «Получить код» — появятся 6 цифр</li>
                      <li>Нажмите «Перейти в MAX»</li>
                      <li>В ops-боте отправьте код и нажмите «Войти в кабинет сотрудника»</li>
                    </ol>
                  </>
                ) : (
                  <>
                    <p className="max-wizard-status" role="status">
                      {maxWaitStatus === "pending_manager"
                        ? "Код принят. Ждём руководителя в чате MAX…"
                        : maxWaitStatus === "pending_confirm"
                          ? "Подтвердите вход в ops-боте — кабинет откроется здесь"
                          : maxPairCode
                            ? "Отправьте код в ops-бот MAX"
                            : "Подтвердите вход в ops-боте MAX"}
                    </p>
                    {maxPairCode ? (
                      <p className="max-code-block">
                        Код: <strong className="max-pair-code">{maxPairCode}</strong>
                      </p>
                    ) : null}
                    <button
                      type="button"
                      className="max-action-btn"
                      onClick={openMaxChat}
                    >
                      Перейти в MAX
                    </button>
                    <ol className="max-login-steps">
                      <li>Откройте ops-бот «Проверка стажа-Ops»</li>
                      {maxPairCode ? (
                        <>
                          <li>Отправьте код сообщением в чат</li>
                          <li>Нажмите «Войти в кабинет сотрудника»</li>
                        </>
                      ) : (
                        <li>Нажмите «Войти в кабинет сотрудника»</li>
                      )}
                    </ol>
                    {maxWaitStatus === "pending_manager" ? (
                      <p className="hint">
                        Руководитель нажмёт «Разрешить вход» — кабинет откроется сам.
                      </p>
                    ) : (
                      <p className="hint">
                        После кнопки в ops-боте кабинет откроется на этой странице.
                      </p>
                    )}
                    <button type="button" className="ghost" onClick={resetMaxWizard}>
                      Начать заново
                    </button>
                  </>
                )}
              </div>
              <div className="auth-alt-hint">
                <p className="auth-alt-label">Другие способы входа</p>
                <div className="auth-alt-list" role="group" aria-label="Другие способы входа">
                  <button
                    type="button"
                    className="auth-alt-btn"
                    onClick={() => goAuthScreen("email_otp")}
                  >
                    Код на рабочую почту
                  </button>
                </div>
              </div>
            </>
          ) : null}

          {authScreen === "email_otp" ? (
            <>
              {!otpSent ? (
                <form className="auth-form" onSubmit={signIn}>
                  <label htmlFor="email">Рабочий email</label>
                  <input
                    id="email"
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
                <form className="auth-form" onSubmit={verifyOtp}>
                  <label htmlFor="otp">Код с почты</label>
                  <input
                    id="otp"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    required
                    inputMode="numeric"
                    autoComplete="one-time-code"
                  />
                  <button type="submit">Войти</button>
                </form>
              )}
              <p className="hint">
                <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                  ← Войти через MAX
                </button>
              </p>
            </>
          ) : null}

          {authScreen === "register" ? (
            <>
              <p className="lead lead-compact">
                Заполните заявку — администратор получит письмо на{" "}
                <strong>proverkastaza@yandex.ru</strong> и подтвердит доступ. После одобрения
                придёт приглашение на ваш e-mail.
              </p>
              {registerSent ? (
                <p className="notice" role="status">
                  {notice ||
                    "Заявка отправлена. Дождитесь письма с доступом после одобрения администратором."}
                </p>
              ) : (
                <form className="auth-form" onSubmit={requestStaffRegister}>
                  <label htmlFor="reg-name">Имя и фамилия</label>
                  <input
                    id="reg-name"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    autoComplete="name"
                    required
                  />
                  <label htmlFor="reg-email">Рабочий e-mail</label>
                  <input
                    id="reg-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    required
                    placeholder="name@company.ru"
                  />
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
                      <a href={`${SITE_URL}/soglasie/`} target="_blank" rel="noopener noreferrer">
                        СОПД
                      </a>{" "}
                      для рассмотрения заявки
                    </span>
                  </label>
                  <button type="submit" disabled={busy || !registerConsent}>
                    Отправить заявку
                  </button>
                  {notice ? <p className="notice">{notice}</p> : null}
                </form>
              )}
              {!registerSent ? (
                <p className="hint">
                  <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                    ← Уже есть доступ — войти
                  </button>
                </p>
              ) : null}
            </>
          ) : null}

          {authScreen !== "register" && notice ? <p className="notice">{notice}</p> : null}
          {authScreen !== "register" ? (
            <p className="hint auth-staff-hint">
              Нет доступа? Вкладка «Запрос доступа» или попросите администратора добавить вас в разделе «Роли».
            </p>
          ) : null}
        </section>
          <SiteReturnPanel />
        </div>
      </main>
    );
  }

  if (me && !me.is_staff) {
    return (
      <main className="auth-layout auth-layout--split">
        <div className="auth-split">
          <section className="card auth-card">
            <h1>Нет доступа</h1>
            <p className="lead lead-compact">
              Вход выполнен, но роли сотрудника нет. Попросите администратора добавить вас в разделе
              «Роли» — открытой регистрации нет.
            </p>
            <button type="button" className="max-action-btn" onClick={() => void supabase?.auth.signOut()}>
              Выйти
            </button>
          </section>
          <SiteReturnPanel />
        </div>
      </main>
    );
  }

  return (
    <main className={`app-layout${view === "case" ? " app-layout--case" : ""}`}>
      <header className="app-header">
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
              <span>
                Кабинет сотрудника · {me?.role ? labelStaffRole(me.role) : "…"} · {me?.email ?? ""}
              </span>
            </div>
          </BrandHomeLink>
        </div>
        <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
          Выйти
        </button>
      </header>

      <section className="warning" role="note">
        Решение принимает СФР. Результат не гарантирован. Функции кабинета сотрудника не переносятся в мини-приложение MAX (ТЗ-09).
      </section>

      <nav className="tabs" aria-label="Разделы">
        <button type="button" className={view === "dashboard" ? "tab active" : "tab"} onClick={() => { setView("dashboard"); void loadDashboard(); }}>
          Дашборд
        </button>
        <button type="button" className={view === "cases" || view === "case" ? "tab active" : "tab"} onClick={() => { setView("cases"); void loadCases(); }}>
          Реестр дел
        </button>
        {me?.role !== "operator" && (
          <button type="button" className={view === "finance" ? "tab active" : "tab"} onClick={() => void loadFinance()}>
            Финансы
          </button>
        )}
        {(me?.role === "admin" || me?.role === "expert" || me?.role_capabilities?.can_view_analytics) && (
          <button type="button" className={view === "analytics" ? "tab active" : "tab"} onClick={() => void loadAnalytics()}>
            Аналитика
          </button>
        )}
        {(me?.role === "admin" || me?.role_capabilities?.can_manage_roles) && (
          <button type="button" className={view === "roles" ? "tab active" : "tab"} onClick={() => void loadRoles()}>
            Роли
          </button>
        )}
      </nav>

      {notice && (
        <p
          className={`notice notice--sticky${/не удалось|ошибк/i.test(notice) ? " notice--error" : ""}`}
          role="status"
        >
          {notice}
        </p>
      )}

      {view === "dashboard" && dashboard && (
        <section className="stack">
          <h1>Дашборд</h1>
          <p className="lead lead-compact">
            Сегодня: <strong>{dashboard.greeting_priority_count}</strong>{" "}
            {dashboard.greeting_priority_count === 1 ? "действие" : "действий"} с высоким приоритетом.
            Сначала отвечаем клиенту, затем закрываем дедлайны и риски SLA.
          </p>
          <div className="metrics">
            <button type="button" className="metric-card" onClick={() => setQueueFilter("reply")}>
              <span>Требуют моего ответа</span>
              <strong>{dashboard.needs_reply}</strong>
              <em>{dashboard.needs_reply_over_30m} без ответа более 30 мин</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("today")}>
              <span>Дедлайн сегодня</span>
              <strong>{dashboard.deadline_today}</strong>
              <em>Задачи и следующий шаг на сегодня</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("new")}>
              <span>Новые обращения</span>
              <strong>{dashboard.new_leads}</strong>
              <em>Заявки без перевода в работу</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("docs")}>
              <span>Ожидаем документы</span>
              <strong>{dashboard.waiting_docs}</strong>
              <em>
                {dashboard.waiting_docs_max_days > 0
                  ? `самое долгое ожидание ${dashboard.waiting_docs_max_days} дн.`
                  : "ИЛС, трудовая, справки, согласие"}
              </em>
            </button>
            <button type="button" className="metric-card" onClick={() => void loadFinance({ queue: "payable" })}>
              <span>Ожидаем оплату</span>
              <strong>{dashboard.payments_pending} / {formatRub(dashboard.payments_pending_amount)}</strong>
              <em>
                Оплачено сегодня: {dashboard.payments_paid_today} / {formatRub(dashboard.payments_paid_today_amount)}
                {" · "}счета на вкладке Финансы
              </em>
            </button>
            <button type="button" className={`metric-card ${dashboard.sla_risk > 0 ? "metric-card--risk" : ""}`} onClick={() => setQueueFilter("sla")}>
              <span>Риск SLA</span>
              <strong>{dashboard.sla_risk}</strong>
              <em>Срок ответа сотрудника нарушен</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("conflicts")}>
              <span>Конфликты каналов</span>
              <strong>{dashboard.channel_conflicts}</strong>
              <em>Предпочтение MAX/веб без привязки. Без MAX / без веб: {dashboard.unlinked_max} / {dashboard.unlinked_web}</em>
            </button>
          </div>

          <div className="dashboard-split">
            <div className="panel">
              <h2>Мои задачи сегодня</h2>
              {dashboard.my_tasks_today.length === 0 ? (
                <p className="hint">Срочных задач нет — можно разобрать стандартную очередь.</p>
              ) : (
                <ul className="plain-list task-list">
                  {dashboard.my_tasks_today.map((item) => (
                    <li key={item.case_id}>
                      <button type="button" className="linkish" onClick={() => void openCase(item.case_id)}>
                        <strong>{formatWhen(item.next_action_at)}</strong>
                        {" · "}
                        {item.client_name ?? "Клиент"} — {item.next_action}
                </button>
              </li>
            ))}
          </ul>
              )}
            </div>
            <div className="panel">
              <h2>Контроль сроков ответа</h2>
              <p className="hint">Ожидание архива, СФР или документов клиента не считается «без ответа».</p>
              <ul className="plain-list sla-list">
                <li className="tone-risk">Просрочено: {dashboard.sla_control.overdue ?? 0}</li>
                <li className="tone-warn">Ответ нужен в 1 час: {dashboard.sla_control.due_1h ?? 0}</li>
                <li className="tone-today">Ответ нужен сегодня: {dashboard.sla_control.due_today ?? 0}</li>
                <li className="tone-wait">Ожидаем клиента / архив / СФР: {dashboard.sla_control.waiting_external ?? 0}</li>
                <li className="tone-muted">На паузе: {dashboard.sla_control.paused ?? 0}</li>
              </ul>
            </div>
          </div>

          <div className="panel">
            <h2>Статус документов</h2>
            <div className="chip-row">
              {Object.entries(DOC_STATUS_LABELS).map(([key, label]) => {
                const count = dashboard.doc_status[key] ?? 0;
                return (
                <button
                    key={key}
                  type="button"
                    className={queueFilter === `doc:${key}` ? "chip active" : "chip"}
                    onClick={() => setQueueFilter(`doc:${key}`)}
                >
                    {label} — {count}
                </button>
                );
              })}
            </div>
          </div>

          <div className="panel">
            <h2>Рабочая очередь</h2>
            <div className="chip-row">
              {[
                ["all", "Все"],
                ["urgent", "Срочно"],
                ["today", "Сегодня"],
                ["reply", "Мой ответ"],
                ["docs", "Документы"],
                ["payment", "Оплата"],
                ["sla", "Риск SLA"],
              ].map(([id, label]) => (
                  <button
                  key={id}
                    type="button"
                  className={queueFilter === id ? "chip active" : "chip"}
                  onClick={() => setQueueFilter(id)}
                  >
                  {label}
                  </button>
              ))}
          </div>
            <div className="queue-wrap">
              <table className="queue-table">
                <thead>
                  <tr>
                    <th>Приоритет</th>
                    <th>Дело</th>
                    <th>Этап</th>
                    <th>Последнее событие</th>
                    <th>Следующий шаг</th>
                    <th>Дедлайн</th>
                    <th>Канал</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard.work_queue || [])
                    .filter((item) => {
                      if (queueFilter === "all") return true;
                      if (queueFilter === "urgent") return item.priority === "urgent";
                      if (queueFilter === "today") return item.priority === "today" || item.deadline_status === "today";
                      if (queueFilter === "reply") return item.waiting_on === "staff";
                      if (queueFilter === "docs") return item.waiting_on === "client" || item.waiting_on === "archive";
                      if (queueFilter === "payment") return item.waiting_on === "payment";
                      if (queueFilter === "sla") return item.deadline_status === "overdue";
                      if (queueFilter === "new") return item.pipeline_status === "intake" || item.b2c_status === "lead";
                      if (queueFilter === "conflicts") return item.channel !== "unset";
                      if (queueFilter.startsWith("doc:")) {
                        const key = queueFilter.slice(4);
                        return Boolean(item.doc_flags?.[key]);
                      }
                      return true;
                    })
                    .map((item) => (
                      <tr key={item.case_id} className={`tone-${item.deadline_status}`}>
                        <td>{PRIORITY_LABELS[item.priority]}</td>
                        <td>{item.client_name ?? "Клиент"}</td>
                        <td>{labelPipeline(item.pipeline_status)}</td>
                        <td>{item.last_event}</td>
                        <td>{item.next_action}</td>
                        <td>
                          <span className={`deadline deadline--${item.deadline_status}`}>
                            {formatWhen(item.next_action_at)}
                          </span>
                        </td>
                        <td>{CHANNEL_LABELS[item.channel] ?? item.channel}</td>
                        <td>
                          <button type="button" className="ghost" onClick={() => void openCase(item.case_id)}>
                            Открыть
                  </button>
                        </td>
                      </tr>
              ))}
                </tbody>
              </table>
            </div>
          </div>

              <div className="panel">
            <h2>Дела по этапам</h2>
                <ul className="plain-list">
              {Object.entries(dashboard.by_pipeline).map(([k, v]) => (
                <li key={k}>{labelPipeline(k)}: {v}</li>
                  ))}
                </ul>
              </div>
        </section>
      )}

      {view === "cases" && (
        <CasesRegistry
          cases={cases}
          meUserId={me?.user_id ?? ""}
          meRole={me?.role ?? null}
          q={q}
          onQ={setQ}
          filterPipeline={filterPipeline}
          onFilterPipeline={setFilterPipeline}
          filterChannel={filterChannel}
          onFilterChannel={setFilterChannel}
          filterPackage={filterPackage}
          onFilterPackage={setFilterPackage}
          packageOptions={[
            { value: "DIAG", label: "Диагностика" },
            { value: "ACCOMP", label: "Сопровождение" },
            { value: "SF_LUMP", label: labelPackage("SF_LUMP") },
            { value: "SF_MONTH", label: labelPackage("SF_MONTH") },
          ]}
          pipelineOptions={pipelineStageOptions(PIPELINE_FILTER_STAGES)}
          queue={registryQueue}
          onQueue={(next) => {
            setRegistryQueue(next);
            void loadCases({ queue: next });
          }}
          busy={busy}
          loading={casesLoading}
          onSearch={() => void loadCases()}
          onPreview={setPreviewId}
          onOpen={(id) => void openCase(id)}
          onWriteMax={(id) => void openCase(id, { focusMaxReply: true })}
          onTake={(id) => void takeCase(id)}
          onSuggest={(id) => void suggestStep(id)}
          onRequestDocs={(id) => void requestDocsFor(id)}
          onMarkTest={(id, isTest) => void markTest(id, isTest)}
          onOpenFinance={(opts) => void loadFinance(opts)}
          preview={previewId ? buildPreviewFromSummary(cases.find((c) => c.id === previewId) ?? {
            id: previewId,
            pipeline_status: "",
            b2c_status: "",
            client_name: null,
            client_phone: null,
            expert_user_id: null,
            preferred_channel: "unset",
            max_linked: false,
            web_linked: false,
          }) : null}
          previewLoading={false}
        />
      )}

      {view === "case" && detail && (
        <section className="case-page">
          <CaseFunnelMain
            detail={detail}
            meUserId={me?.user_id ?? null}
            busy={busy}
            nextActionText={nextActionText}
            nextActionAt={nextActionAt}
            waitingOn={waitingOn}
            pipelineStatus={pipelineStatus}
            checklistTitle={checklistTitle}
            beforeRub={beforeRub}
            afterRub={afterRub}
            lumpRub={lumpRub}
            sfrReceived={sfrReceived}
            orderCode={orderCode}
            orderAmount={orderAmount}
            feedbackText={feedbackText}
            feedbackQuality={feedbackQuality}
            repEmail={repEmail}
            stepHint={stepHint}
            stepMessages={stepMessages}
            chatMessages={messages}
            onBack={() => setView("cases")}
            onPrevCase={() => {
              const ids = cases.map((c) => c.id);
              const idx = ids.indexOf(detail.id);
              if (idx > 0) void openCase(ids[idx - 1]);
            }}
            onNextCase={() => {
              const ids = cases.map((c) => c.id);
              const idx = ids.indexOf(detail.id);
              if (idx >= 0 && idx < ids.length - 1) void openCase(ids[idx + 1]);
            }}
            canPrevCase={cases.findIndex((c) => c.id === detail.id) > 0}
            canNextCase={(() => {
              const idx = cases.findIndex((c) => c.id === detail.id);
              return idx >= 0 && idx < cases.length - 1;
            })()}
            onNextActionText={setNextActionText}
            onNextActionAt={setNextActionAt}
            onWaitingOn={setWaitingOn}
            onSaveNextAction={() => void saveNextAction()}
            onSaveArchivePrep={(p) => void saveArchivePrep(p)}
            onCloseCase={(p) => void closeCase(p)}
            onSuggestStep={() => void suggestStep(detail.id)}
            onApplyChatMessage={applyStepMessageToChat}
            onDismissHint={() => {
              setStepHint(null);
              setStepMessages([]);
            }}
            onTake={() => void takeCase(detail.id)}
            onFocusMax={focusMaxReplyPanel}
            onOpenFinance={() =>
              void loadFinance({
                caseId: detail.id,
                queue:
                  waitingOn === "payment" ||
                  (detail.orders ?? []).some((o) =>
                    ["pending", "awaiting_payment", "invoice_sent", "invoice_ready", "pending_payment"].includes(
                      String(o.status || ""),
                    ),
                  )
                    ? "payable"
                    : "awaiting_invoice",
              })
            }
            onRequestReview={() => void requestReview()}
            onCreateTelemost={() => void createTelemost()}
            onSendEmail={() => void sendWorkspaceEmail()}
            onOpenTrackerModal={() => {
              setTrackerModalOpen(true);
              setTrackerDesc("");
              setTrackerTitle("");
              setTrackerForceNew(false);
            }}
            onOpenSigned={(docId) => void openSigned(docId)}
            onUploadDiagnosisReport={(file) => void uploadDiagnosisReport(file)}
            onPublishDiagnosis={(documentId) => void publishDiagnosis(documentId)}
            onToggleChecklist={(id, status) => void toggleChecklist(id, status)}
            onAddChecklist={(e) => void addChecklist(e)}
            onChecklistTitle={setChecklistTitle}
            onPipelineStatus={setPipelineStatus}
            onSavePipeline={() => void savePipeline()}
            onConfirmResult={(e) => void confirmResult(e)}
            onBeforeRub={setBeforeRub}
            onAfterRub={setAfterRub}
            onLumpRub={setLumpRub}
            onSfrReceived={setSfrReceived}
            onOrderCode={setOrderCode}
            onOrderAmount={setOrderAmount}
            onCreateOrder={(e) => void createOrder(e)}
            onSendPayLink={(orderId) => void sendPayLinkForCaseOrder(orderId)}
            onCopyPayLink={(orderId) => void copyPayLinkForCaseOrder(orderId)}
            onRecordServiceConsent={() => void recordServiceConsent()}
            onFeedbackText={setFeedbackText}
            onFeedbackQuality={setFeedbackQuality}
            onSendFeedback={(e) => void sendFeedback(e)}
            onRepEmail={setRepEmail}
            onAddRepresentative={(e) => void addRepresentative(e)}
            onRemoveRepresentative={(userId) => void removeRepresentative(userId)}
          />

          <CaseChatPanel
            messages={messages}
            clientName={detail.client.full_name ?? null}
            caseLabel={caseCatalogLabel(detail.id)}
            maxLinked={Boolean(detail.client.max_linked)}
            maxUserId={detail.client.max_user_id ?? null}
            maxBusinessUrl={detail.channels.max_ops_bot_url ?? detail.channels.max_reply_url ?? null}
            body={maxReplyBody}
            onBodyChange={setMaxReplyBody}
            busy={busy}
            onSendMax={() => void sendMaxReply()}
            onSendInternal={() => void sendMessage()}
            suggestions={replySuggestions}
            onSuggest={() => void suggestReplies()}
            composerHighlight={composerFlash || maxReplyFocus}
            marketingConsentLabel={marketingConsentLabel}
            onRequestMarketingConsent={() => void requestMarketingConsent()}
            waitingOn={waitingOn}
          />
          {trackerModalOpen && detail ? (
            <div className="dup-dialog-backdrop" role="dialog" aria-modal="true">
              <div className="dup-dialog" style={{ maxWidth: 520 }}>
                <h3>Создать задачу в Tracker</h3>
                <p className="hint" style={{ color: "#b91c1c" }}>
                  Не указывайте ФИО, телефон, e-mail, СНИЛС, номера документов, ссылки на кабинет,
                  файлы, текст переписки или содержание ИЛС.
                </p>
                <div className="stack-form">
                  <label>
                    Тип
                    <select
                      value={trackerIssueType}
                      onChange={(e) => setTrackerIssueType(e.target.value)}
                    >
                      <option value="bug">Ошибка</option>
                      <option value="sla_incident">Инцидент SLA</option>
                      <option value="channel_conflict">Конфликт каналов</option>
                      <option value="process_improvement">Улучшение процесса</option>
                      <option value="development">Разработка</option>
                      <option value="content">Контент</option>
                      <option value="security_privacy">Безопасность / ПДн</option>
                      <option value="analytics_hypothesis">Аналитическая гипотеза</option>
                      <option value="partner_request">Партнёрский запрос</option>
                    </select>
                  </label>
                  <label>
                    Приоритет
                    <select
                      value={trackerPriority}
                      onChange={(e) => setTrackerPriority(e.target.value)}
                    >
                      <option value="critical">Критический</option>
                      <option value="high">Высокий</option>
                      <option value="normal">Обычный</option>
                      <option value="low">Низкий</option>
                    </select>
                  </label>
                  <label>
                    Направление
                    <select
                      value={trackerDirection}
                      onChange={(e) => setTrackerDirection(e.target.value)}
                    >
                      <option value="ops">Операции</option>
                      <option value="product">Продукт</option>
                      <option value="dev">Разработка</option>
                      <option value="content">Контент</option>
                      <option value="security">Безопасность</option>
                      <option value="partners">Партнёры</option>
                    </select>
                  </label>
                  <label>
                    Повторяемость
                    <select value={trackerRepeat} onChange={(e) => setTrackerRepeat(e.target.value)}>
                      <option value="once">Единично</option>
                      <option value="recurring">Повторяется</option>
                      <option value="systemic">Системно</option>
                    </select>
                  </label>
                  <label>
                    Краткий заголовок (опционально)
                    <input
                      value={trackerTitle}
                      onChange={(e) => setTrackerTitle(e.target.value)}
                      placeholder="Без ПДн"
                      maxLength={120}
                    />
                  </label>
                  <label>
                    Обезличенное описание
                    <textarea
                      rows={5}
                      value={trackerDesc}
                      onChange={(e) => setTrackerDesc(e.target.value)}
                      placeholder="Что не так / что улучшить — без персональных данных"
                      required
                    />
                  </label>
                  <label className="inline-form">
                    <input
                      type="checkbox"
                      checked={trackerForceNew}
                      onChange={(e) => setTrackerForceNew(e.target.checked)}
                    />
                    Создать новую, даже если есть открытая того же типа
                  </label>
                  <p className="hint">
                    В Tracker уйдёт псевдоним дела (case_ref), этап {detail.pipeline_status}, тип и
                    описание. Очередь STAZH.
                  </p>
                </div>
                <div className="dup-dialog-actions">
                  <button type="button" className="ghost" onClick={() => setTrackerModalOpen(false)}>
                    Отмена
                  </button>
                  <button type="button" disabled={busy} onClick={() => void createTrackerIssue()}>
                    Создать в Tracker
                  </button>
                </div>
              </div>
            </div>
          ) : null}
          {dupDialog ? (
            <div className="dup-dialog-backdrop" role="dialog" aria-modal="true">
              <div className="dup-dialog">
                <h3>Повтор сообщения</h3>
                <p>
                  Этот запрос уже отправлялся
                  {dupDialog.lastAt
                    ? ` ${new Date(dupDialog.lastAt).toLocaleString("ru-RU", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}`
                    : " сегодня"}
                  .
                </p>
                {dupDialog.preview ? (
                  <p className="hint">{dupDialog.preview}</p>
                ) : null}
                <div className="dup-dialog-actions">
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      setDupDialog(null);
                      setMaxReplyFocus(true);
                      document.getElementById("max-reply-panel")?.scrollIntoView({
                        behavior: "smooth",
                      });
                    }}
                  >
                    Открыть последнее
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      const needExtra =
                        dupDialog.code === "duplicate_message_limit" ||
                        (dupDialog.count48h ?? 0) >= 2;
                      if (
                        needExtra &&
                        !window.confirm(
                          "Похожих сообщений уже несколько за 48 часов. Отправить повторно?",
                        )
                      ) {
                        return;
                      }
                      void sendMaxReply({ force: true });
                    }}
                  >
                    Отправить повторно
                  </button>
                  <button type="button" className="ghost" onClick={() => setDupDialog(null)}>
                    Отменить
                  </button>
          </div>
              </div>
            </div>
          ) : null}
        </section>
      )}

      {view === "finance" && (
        <>
          <FinancePanel
            data={finance}
            loading={financeLoading}
            busy={busy}
            canManage={me?.role === "admin"}
            meRole={me?.role ?? null}
            q={financeQ}
            onQ={setFinanceQ}
            queue={financeQueue}
            onQueue={(value) => {
              void loadFinance({ queue: value });
            }}
            period={financePeriod}
            onPeriod={setFinancePeriod}
            packageCode={financePackage}
            onPackageCode={setFinancePackage}
            includeTest={financeIncludeTest}
            onIncludeTest={setFinanceIncludeTest}
            onSearch={() => void loadFinance({ queue: financeQueue })}
            onCreate={() => setCreateInvoiceOpen(true)}
            onCreateForCase={(caseId) => {
              setInvoiceCaseId(caseId);
              setCreateInvoiceOpen(true);
            }}
            onOpenCase={(caseId) => void openCase(caseId)}
            onClearCaseFilter={
              financeQ.trim()
                ? () => {
                    setFinanceQ("");
                    void loadFinance({ queue: financeQueue, q: "" });
                  }
                : undefined
            }
            caseFilterActive={Boolean(financeQ.trim())}
            onCopyLink={(order) => void copyPayLink(order)}
            onSendLink={(order) => void sendPayLink(order)}
            onRemind={(order, sendMax) => void remindPayment(order, sendMax)}
            onMarkPaid={(order) => {
              setMarkPaidOrder(order);
              setPaidAmount(String(order.amount_rub));
              setPaidAt("");
              setPaidRef("");
            }}
            onCancel={(order) => {
              setCancelOrder(order);
              setCancelReason("refusal");
              setCancelComment("");
            }}
          />

          {createInvoiceOpen && (
            <section className="panel stack finance-modal">
              <h2>Создать счёт</h2>
              <form className="stack-form" onSubmit={(e) => void createFinanceInvoice(e)}>
                <label>
                  Дело
                  <select value={invoiceCaseId} onChange={(e) => setInvoiceCaseId(e.target.value)} required>
                    <option value="">Выберите дело</option>
                    {cases.filter((c) => !c.is_test).map((c) => (
                      <option key={c.id} value={c.id}>{c.client_name ?? "Клиент"} · {c.id.slice(0, 8)}</option>
                    ))}
                </select>
                </label>
                <label>
                  Услуга с /tarify/
                  <select
                    value={`${invoiceCode}:${invoiceAmount}:${invoiceLabel}`}
                    onChange={(e) => {
                      const [code, amount, ...rest] = e.target.value.split(":");
                      setInvoiceCode((code as "DIAG" | "ACCOMP") || "DIAG");
                      setInvoiceAmount(amount || "3000");
                      setInvoiceLabel(rest.join(":") || "Диагностика");
                    }}
                  >
                    <option value="DIAG:3000:Диагностика">Диагностика · 3 000 ₽</option>
                    <option value="ACCOMP:5000:Подготовка документов">Подготовка документов · 5 000 ₽</option>
                    <option value="ACCOMP:8000:Сопровождение до подачи">Сопровождение до подачи · 8 000 ₽</option>
                  </select>
                </label>
                <label>Сумма ₽<input type="number" min={1} step="0.01" value={invoiceAmount} onChange={(e) => setInvoiceAmount(e.target.value)} required /></label>
                <label>Срок оплаты<input type="datetime-local" value={invoiceDue} onChange={(e) => setInvoiceDue(e.target.value)} /></label>
                <p className="hint">Оплата за информационно-документарную поддержку согласно выбранной услуге/договору.</p>
                <div className="inline-form">
                  <button type="submit">Сохранить черновик</button>
                  <button type="button" className="ghost" onClick={() => setCreateInvoiceOpen(false)}>Отмена</button>
            </div>
              </form>
            </section>
          )}

          {markPaidOrder && (
            <section className="panel stack finance-modal">
              <h2>Отметить оплату вручную</h2>
              <form className="stack-form" onSubmit={(e) => void submitMarkPaid(e)}>
                <label>Дата и время<input type="datetime-local" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} required /></label>
                <label>Сумма ₽<input type="number" min={1} step="0.01" value={paidAmount} onChange={(e) => setPaidAmount(e.target.value)} required /></label>
                <label>
                  Способ
                  <select value={paidMethod} onChange={(e) => setPaidMethod(e.target.value)}>
                    <option value="transfer">Перевод</option>
                    <option value="card">Карта</option>
                    <option value="yookassa">ЮKassa</option>
                    <option value="cash">Наличные</option>
                    <option value="other">Другое</option>
                </select>
                </label>
                <label>Номер операции / комментарий<input value={paidRef} onChange={(e) => setPaidRef(e.target.value)} required /></label>
                <p className="hint">Сотрудник и время попадут в журнал аудита. Удалить запись через интерфейс нельзя.</p>
                <div className="inline-form">
                  <button type="submit">Записать оплату</button>
                  <button type="button" className="ghost" onClick={() => setMarkPaidOrder(null)}>Отмена</button>
            </div>
            </form>
        </section>
      )}

          {cancelOrder && (
            <section className="panel stack finance-modal">
              <h2>Отменить счёт</h2>
              <form className="stack-form" onSubmit={(e) => void submitCancel(e)}>
                <label>
                  Причина
                  <select value={cancelReason} onChange={(e) => setCancelReason(e.target.value)}>
                    <option value="refusal">Отказ</option>
                    <option value="duplicate">Дубль</option>
                    <option value="amount_error">Ошибка суммы</option>
                    <option value="no_contact">Нет связи</option>
                    <option value="other">Другое</option>
                  </select>
                </label>
                <label>Комментарий<input value={cancelComment} onChange={(e) => setCancelComment(e.target.value)} /></label>
                <div className="inline-form">
                  <button type="submit">Отменить счёт</button>
                  <button type="button" className="ghost" onClick={() => setCancelOrder(null)}>Закрыть</button>
                </div>
              </form>
        </section>
          )}
        </>
      )}

      {view === "analytics" && analytics && token && (
        <AdminAnalyticsPanel
          data={analytics}
          filters={analyticsFilters}
          onFiltersChange={setAnalyticsFilters}
          onReload={() => void loadAnalytics(analyticsFilters)}
          onOpenRegistry={openRegistryFromAnalytics}
          showFinance={me?.role === "admin"}
          apiBase={apiBase}
          token={token}
          busy={busy}
          onNotice={setNotice}
        />
      )}

      {view === "roles" && token && (
        <StaffRolesPanel
          token={token}
          meUserId={me?.user_id ?? ""}
          apiFetch={apiFetch}
          onNotice={setNotice}
        />
      )}

      {busy && <p className="hint">Загрузка…</p>}
    </main>
  );
}
