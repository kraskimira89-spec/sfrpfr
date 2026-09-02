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
import { IngestReviewPanel } from "@/components/ingest-review-panel";
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

/** ╨н╨║╤А╨░╨╜ ╨▓╤Е╨╛╨┤╨░: MAX (╨╛╤Б╨╜╨╛╨▓╨╜╨╛╨╣) | ╨║╨╛╨┤ ╨╜╨░ ╨┐╨╛╤З╤В╤Г | ╨╖╨░╤П╨▓╨║╨░ ╨╜╨░ ╨┤╨╛╤Б╤В╤Г╨┐. */
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
      title="╨Э╨░ ╨│╨╗╨░╨▓╨╜╤Г╤О"
      aria-label="╨Э╨░ ╨│╨╗╨░╨▓╨╜╤Г╤О"
    >
      {children}
    </a>
  );
}

function SiteReturnPanel() {
  return (
    <a className="auth-return-panel" href={SITE_URL}>
      <span className="auth-return-panel__title">╨Т╨╡╤А╨╜╤Г╤В╤М╤Б╤П ╨╜╨░ ╤Б╨░╨╣╤В</span>
      <span className="auth-return-panel__hint">proverkastaza.ru</span>
    </a>
  );
}

const CHANNEL_LABELS: Record<string, string> = {
  max_miniapp: "MAX",
  web_cabinet: "╨Т╨╡╨▒-╨║╨░╨▒╨╕╨╜╨╡╤В",
  unset: "╨╜╨╡ ╨▓╤Л╨▒╤А╨░╨╜",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: "╨б╤А╨╛╤З╨╜╨╛",
  today: "╨б╨╡╨│╨╛╨┤╨╜╤П",
  standard: "╨б╤В╨░╨╜╨┤╨░╤А╤В╨╜╨╛",
};

const DOC_STATUS_LABELS: Record<string, string> = {
  consent_missing: "╨Э╨╡╤В ╤Б╨╛╨│╨╗╨░╤Б╨╕╤П ╨╜╨░ ╨Я╨Ф╨╜",
  ils_missing: "╨Э╨╡ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨░ ╨▓╤Л╨┐╨╕╤Б╨║╨░ ╨Ш╨Ы╨б",
  labor_missing: "╨Э╨╡ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨░ ╤В╤А╤Г╨┤╨╛╨▓╨░╤П",
  archive_needed: "╨Ю╨╢╨╕╨┤╨░╨╡╨╝ ╨░╤А╤Е╨╕╨▓╨╜╤Г╤О ╤Б╨┐╤А╨░╨▓╨║╤Г",
  discrepancy: "╨а╨░╤Б╤Е╨╛╨╢╨┤╨╡╨╜╨╕╤П ╨Ш╨Ы╨б ╨╕ ╤В╤А╤Г╨┤╨╛╨▓╨╛╨╣",
  extra_info: "╨Э╤Г╨╢╨╜╨░ ╨╕╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╤П ╨╛╤В ╨║╨╗╨╕╨╡╨╜╤В╨░",
  project_ready: "╨Я╤А╨╛╨╡╨║╤В ╨╛╨▒╤А╨░╤Й╨╡╨╜╨╕╤П ╨│╨╛╤В╨╛╨▓",
  sfr_reply: "╨Ю╤В╨▓╨╡╤В ╨б╨д╨а тАФ ╨╜╤Г╨╢╨╡╨╜ ╤А╨░╨╖╨▒╨╛╤А",
};

function formatRub(value: number): string {
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(value || 0))} тВ╜`;
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return "тАФ";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "тАФ";
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
      /* ╨╛╤Б╤В╨░╨▓╨╕╤В╤М ╤Б╤Л╤А╨╛╨╣ ╤В╨╡╨║╤Б╤В */
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
      /* ╨╛╤Б╤В╨░╨▓╨╕╤В╤М ╤Б╤Л╤А╨╛╨╣ ╤В╨╡╨║╤Б╤В */
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
  const [invoiceLabel, setInvoiceLabel] = useState("╨Ф╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░");
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
      setNotice("╨Э╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐╨░: ╤В╤А╨╡╨▒╤Г╨╡╤В╤Б╤П ╤А╨╛╨╗╤М ╨╛╨┐╨╡╤А╨░╤В╨╛╤А╨░, ╤Н╨║╤Б╨┐╨╡╤А╤В╨░ ╨╕╨╗╨╕ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░.");
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
        setNotice("╨Э╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐╨░ ╨╕╨╗╨╕ API ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜.");
      }
    })();
  }, [token, loadMe, loadDashboard, loadCases]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setNotice("╨Ъ╨░╨▒╨╕╨╜╨╡╤В ╨╡╤Й╤С ╨╜╨╡ ╨╜╨░╤Б╤В╤А╨╛╨╡╨╜: ╨╜╨╡╤В public ╨║╨╗╤О╤З╨░ Supabase.");
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
          ? "╨Я╨╛╤З╤В╨░ ╨╜╨╡ ╨╖╨░╤А╨╡╨│╨╕╤Б╤В╤А╨╕╤А╨╛╨▓╨░╨╜╨░ ╨┤╨╗╤П ╨▓╤Е╨╛╨┤╨░. ╨Я╨╛╨┐╤А╨╛╤Б╨╕╤В╨╡ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░ ╨▓╤Л╨┤╨░╤В╤М ╤А╨╛╨╗╤М (staff-grant) ╨╕╨╗╨╕ ╨▓╨╛╨╣╨┤╨╕╤В╨╡ ╤З╨╡╤А╨╡╨╖ MAX."
          : `╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨║╨╛╨┤: ${error.message}`;
      setNotice(msg);
      return;
    }
    setOtpSent(true);
    setNotice("╨Ъ╨╛╨┤ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜ ╨╜╨░ ╤А╨░╨▒╨╛╤З╨╕╨╣ email.");
  }

  async function requestMaxLogin(): Promise<boolean> {
    if (!apiBase) {
      setNotice("API ╨╜╨╡ ╨╜╨░╤Б╤В╤А╨╛╨╡╨╜.");
      return false;
    }
    if (!email.trim() || !email.includes("@")) {
      setNotice("╨г╨║╨░╨╢╨╕╤В╨╡ ╤А╨░╨▒╨╛╤З╨╕╨╣ email тАФ ╤А╨╛╨╗╤М ╨┤╨╛╨╗╨╢╨╜╨░ ╨▒╤Л╤В╤М ╤Г╨╢╨╡ ╨▓╤Л╨┤╨░╨╜╨░ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝.");
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
          typeof body.detail === "string" ? body.detail : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╜╨░╤З╨░╤В╤М ╨▓╤Е╨╛╨┤ ╤З╨╡╤А╨╡╨╖ MAX.",
        );
      }
      setMaxTicket(body.ticket || "");
      setMaxPairCode(body.pair_code || "");
      setMaxWaitStatus(body.status || "pending_pair");
      if (body.max_bot_url) setMaxBotUrl(body.max_bot_url);
      setOtpSent(true);
      setNotice(
        body.message ||
          "╨Ъ╨╛╨┤ ╨┐╨╛╤П╨▓╨╕╨╗╤Б╤П ╨╜╨╕╨╢╨╡. ╨Э╨░╨╢╨╝╨╕╤В╨╡ ┬л╨Я╨╡╤А╨╡╨╣╤В╨╕ ╨▓ MAX┬╗, ╨╛╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╨║╨╛╨┤ ╨▓ ops-╨▒╨╛╤В ╨╕ ╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╨╡ ╨▓╤Е╨╛╨┤.",
      );
      return true;
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╜╨░╤З╨░╤В╤М ╨▓╤Е╨╛╨┤ ╤З╨╡╤А╨╡╨╖ MAX.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function getMaxLoginCode() {
    if (!email.trim() || !email.includes("@")) {
      setNotice("╨б╨╜╨░╤З╨░╨╗╨░ ╤Г╨║╨░╨╢╨╕╤В╨╡ ╤А╨░╨▒╨╛╤З╨╕╨╣ email.");
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
      setNotice("╨Ю╤В╨╝╨╡╤В╤М╤В╨╡ ╤Б╨╛╨│╨╗╨░╤Б╨╕╨╡ ╤Б ╨б╨Ю╨Я╨Ф тАФ ╨▒╨╡╨╖ ╨╜╨╡╨│╨╛ ╨╖╨░╤П╨▓╨║╤Г ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨╜╨╡╨╗╤М╨╖╤П.");
      return;
    }
    if (!fullName.trim()) {
      setNotice("╨г╨║╨░╨╢╨╕╤В╨╡ ╨╕╨╝╤П ╨╕ ╤Д╨░╨╝╨╕╨╗╨╕╤О.");
      return;
    }
    if (!email.trim() || !email.includes("@")) {
      setNotice("╨г╨║╨░╨╢╨╕╤В╨╡ ╤А╨░╨▒╨╛╤З╨╕╨╣ e-mail.");
      return;
    }
    if (!apiBase) {
      setNotice("API ╨║╨░╨▒╨╕╨╜╨╡╤В╨░ ╨╜╨╡ ╨╜╨░╤Б╤В╤А╨╛╨╡╨╜.");
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
          "╨Ч╨░╤П╨▓╨║╨░ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨░. ╨Я╨╛╤Б╨╗╨╡ ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╤П ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝ ╨╜╨░ proverkastaza@yandex.ru ╨▓╤Л ╨┐╨╛╨╗╤Г╤З╨╕╤В╨╡ ╨┐╨╕╤Б╤М╨╝╨╛ ╤Б ╨┤╨╛╤Б╤В╤Г╨┐╨╛╨╝.",
      );
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨╖╨░╤П╨▓╨║╤Г.");
    } finally {
      setBusy(false);
    }
  }

  // ╨Я╨Ъ ╨╢╨┤╤С╤В: ╨║╨╛╨┤ ╨▓ MAX тЖТ (╨┐╤А╨╕ ╨┐╨╡╤А╨▓╨╛╨╝ ╨▓╤Е╨╛╨┤╨╡) ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤М тЖТ ╤Б╨╡╤Б╤Б╨╕╤П
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
            setNotice(body.message || "╨Т╤А╨╡╨╝╤П ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╤П ╨╕╤Б╤В╨╡╨║╨╗╨╛. ╨Э╨░╤З╨╜╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╤Б╨╜╨╛╨▓╨░.");
          }
        } catch (err) {
          if (!cancelled) {
            setNotice(err instanceof Error ? err.message : "╨Ю╤И╨╕╨▒╨║╨░ ╨╛╨╢╨╕╨┤╨░╨╜╨╕╤П ╨▓╤Е╨╛╨┤╨░.");
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
    setNotice(error ? "╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╨║╨╛╨┤." : "");
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
        // ╨Ъ╨░╤А╤В╨╛╤З╨║╨░ ╨┤╨╡╨╗╨░ ╨▓╨░╨╢╨╜╨╡╨╡ тАФ ╨┐╨╡╤А╨╡╨┐╨╕╤Б╨║╨░ ╨╝╨╛╨╢╨╡╤В ╨▒╤Л╤В╤М ╨┐╤Г╤Б╤В╨╛╨╣ ╨╜╨░ intake.
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
          ? "╨Ф╨╡╨╗╨╛ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╨╛ ╨╕╨╗╨╕ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛ ╨┤╨╗╤П ╨▓╨░╤И╨╡╨╣ ╤А╨╛╨╗╨╕."
          : `╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨║╤А╤Л╤В╤М ╨┤╨╡╨╗╨╛: ${detail || "╨╛╤И╨╕╨▒╨║╨░ API"}`,
      );
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    // ╨б╨╛╤Е╤А╨░╨╜╨╕╤В╤М deep-link ╨┤╨╛ ╨╗╨╛╨│╨╕╨╜╨░ (MAX ╤З╨░╤Б╤В╨╛ ╨╛╤В╨║╤А╤Л╨▓╨░╨╡╤В URL ╨╜╨░ ╤Н╨║╤А╨░╨╜╨╡ ╨▓╤Е╨╛╨┤╨░).
    captureAdminDeepLink();
  }, []);

  useEffect(() => {
    if (!token || !me?.is_staff) return;
    const link = captureAdminDeepLink();
    if (!link?.caseId) return;
    let cancelled = false;
    void (async () => {
      // Deep-link ╨╕╨╖ ops ┬л╨║╨╗╨╕╨╡╨╜╤В ╨╢╨┤╤С╤В┬╗ / ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В ╨▓ ╤З╨░╤В тЖТ ╨┤╨╡╨╗╨╛ + ╤З╨░╤В.
      const ok = await openCase(link.caseId, { focusMaxReply: true });
      if (ok && !cancelled) clearAdminDeepLink();
    })();
    return () => {
      cancelled = true;
    };
    // openCase ╨╖╨░╨╝╤Л╨║╨░╨╡╤В╤Б╤П ╨╜╨░ token/state тАФ ╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ staff-╤Б╨╡╤Б╤Б╨╕╨╕.
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
      setNotice("╨д╨╕╨╜╨░╨╜╤Б╤Л ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╤Л ╨┤╨╗╤П ╤А╨╛╨╗╨╕ ╨╛╨┐╨╡╤А╨░╤В╨╛╤А╨░.");
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
          ? `╨Р╨╜╨░╨╗╨╕╤В╨╕╨║╨░ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░: ${hint}`
          : "╨Р╨╜╨░╨╗╨╕╤В╨╕╨║╨░ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░. ╨Ф╨╗╤П ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░ ╨╕ ╤Б╨┐╨╡╤Ж╨╕╨░╨╗╨╕╤Б╤В╨░ ╤А╨░╨╖╨┤╨╡╨╗ ╨┤╨╛╨╗╨╢╨╡╨╜ ╨╛╤В╨║╤А╤Л╨▓╨░╤В╤М╤Б╤П.",
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
    setNotice("╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╨╖╨░╨┐╤А╨╛╤И╨╡╨╜╨░.");
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
        setNotice(`╨в╨╡╨╗╨╡╨╝╨╛╤Б╤В ╤Б╨╛╨╖╨┤╨░╨╜: ${result.join_url}`);
        await openCase(detail.id);
      } else if (result.skipped) {
        setNotice("╨в╨╡╨╗╨╡╨╝╨╛╤Б╤В ╨┐╤А╨╛╨┐╤Г╤Й╨╡╨╜ (╨╜╨╡╤В ╤В╨╛╨║╨╡╨╜╨░ / ╨▓╤Л╨║╨╗╤О╤З╨╡╨╜).");
      } else {
        setNotice(
          `╨в╨╡╨╗╨╡╨╝╨╛╤Б╤В: ${result.error || "╨╛╤И╨╕╨▒╨║╨░"}${result.hint ? ` тАФ ${result.hint}` : ""}`,
        );
      }
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╨╖╨┤╨░╤В╤М ╨в╨╡╨╗╨╡╨╝╨╛╤Б╤В.");
    } finally {
      setBusy(false);
    }
  }

  async function createTrackerIssue() {
    if (!token || !detail) return;
    if (trackerDesc.trim().length < 10) {
      setNotice("╨Ю╨┐╨╕╤Б╨░╨╜╨╕╨╡ ╨╖╨░╨┤╨░╤З╨╕: ╨╝╨╕╨╜╨╕╨╝╤Г╨╝ 10 ╤Б╨╕╨╝╨▓╨╛╨╗╨╛╨▓ (╨▒╨╡╨╖ ╨Я╨Ф╨╜).");
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
          ? `╨г╨╢╨╡ ╨╡╤Б╤В╤М ╨╛╤В╨║╤А╤Л╤В╨░╤П ╨╖╨░╨┤╨░╤З╨░: ${result.tracker_issue_key}`
          : `╨б╨╛╨╖╨┤╨░╨╜╨╛ ╨▓ Tracker: ${result.tracker_issue_key}`;
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
          `Tracker: ${(d && typeof d === "object" && d.error) || "╨╛╤И╨╕╨▒╨║╨░"}${
            fields ? ` (${fields})` : ""
          }`,
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "╨╜╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╨╖╨┤╨░╤В╤М";
      setNotice(`Tracker: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function sendWorkspaceEmail() {
    if (!token || !detail) return;
    if (!detail.client.email) {
      setNotice("╨г ╨║╨╗╨╕╨╡╨╜╤В╨░ ╨╜╨╡╤В email тАФ ╨┐╨╕╤Б╤М╨╝╨╛ ╨╜╨╡ ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М.");
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
      if (result.ok) setNotice("╨Я╨╕╤Б╤М╨╝╨╛ ┬л╨╖╨░╨┐╤А╨╛╤Б ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓┬╗ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨╛.");
      else if (result.skipped) setNotice("╨Я╨╛╤З╤В╨░ ╨┐╤А╨╛╨┐╤Г╤Й╨╡╨╜╨░ (╨╜╨╡╤В ╤В╨╛╨║╨╡╨╜╨░ / ╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨░).");
      else setNotice(`╨Я╨╛╤З╤В╨░: ${result.error || "╨╛╤И╨╕╨▒╨║╨░"}`);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨┐╨╕╤Б╤М╨╝╨╛.");
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
      setNotice("╨Ф╨╡╨╗╨╛ ╨▓╨╖╤П╤В╨╛ ╨▓ ╤А╨░╨▒╨╛╤В╤Г.");
      await loadCases();
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨▓╨╖╤П╤В╤М ╨┤╨╡╨╗╨╛ ╨▓ ╤А╨░╨▒╨╛╤В╤Г.");
    } finally {
      setBusy(false);
    }
  }

  async function suggestStep(caseId: string) {
    if (!token) return;
    setBusy(true);
    setNotice("DeepSeek ╨┤╤Г╨╝╨░╨╡╤В ╨╜╨░╨┤ ╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╝ ╤И╨░╨│╨╛╨╝тАж");
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
      // ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╤И╨░╨│ ╨▓ ╨┤╨╡╨╗╨╡, ╨╜╨╛ ╨Э╨Х ╨╛╤В╨┐╤А╨░╨▓╨╗╤П╨╡╨╝ ╤В╨╡╨║╤Б╤В ╨║╨╗╨╕╨╡╨╜╤В╤Г.
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
        "╨Я╨╛╨┤╤Б╨║╨░╨╖╨║╨░ ╨│╨╛╤В╨╛╨▓╨░: ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤В╨╕╨┐ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П ╨╕ ╨╜╨░╨╢╨╝╨╕╤В╨╡ ╨┐╨╛╨┤╤Б╤В╨░╨╜╨╛╨▓╨║╤Г, ╨╖╨░╤В╨╡╨╝ ╨╛╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╨▓ MAX ╨▓╤А╤Г╤З╨╜╤Г╤О.",
      );
      if (view !== "case") {
        await loadCases();
        await loadDashboard();
      }
    } catch (error) {
      setNotice(
        error instanceof Error
          ? `╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╨┐╨╛╨┤╤Б╨║╨░╨╖╨║╤Г ╤И╨░╨│╨░: ${error.message}`
          : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╨┐╨╛╨┤╤Б╨║╨░╨╖╨║╤Г ╤И╨░╨│╨░.",
      );
    } finally {
      setBusy(false);
    }
  }

  function applyStepMessageToChat(text: string, opts?: { confirmAssign?: boolean }) {
    if (opts?.confirmAssign && detail && !detail.expert_user_id) {
      if (!window.confirm("╨Э╨░╨╖╨╜╨░╤З╨╕╤В╤М ╤Б╨╡╨▒╨╡ ╨╕ ╨┐╨╛╨┤╤Б╤В╨░╨▓╨╕╤В╤М ╤В╨╡╨║╤Б╤В ╨▓ ╤З╨░╤В?")) return;
      void takeCase(detail.id);
    }
    setMaxReplyBody(text);
    setReplySuggestions([]);
    setMaxReplyFocus(true);
    setComposerFlash(true);
    window.setTimeout(() => setComposerFlash(false), 2000);
    setNotice("╨в╨╡╨║╤Б╤В ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜ ╨▓ ╤З╨╡╤А╨╜╨╛╨▓╨╕╨║. ╨Ю╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╨┐╨╛╤Б╨╗╨╡ ╨┐╤А╨╛╨▓╨╡╤А╨║╨╕.");
  }

  async function recordServiceConsent() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/service-consent`, token, {
        method: "POST",
      });
      setNotice("╨б╨╛╨│╨╗╨░╤Б╨╕╨╡ ╨║╨╗╨╕╨╡╨╜╤В╨░ ╨╜╨░ ╤Г╤Б╨╗╤Г╨│╤Г ╨╖╨░╤Д╨╕╨║╤Б╨╕╤А╨╛╨▓╨░╨╜╨╛.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╖╨░╤Д╨╕╨║╤Б╨╕╤А╨╛╨▓╨░╤В╤М ╤Б╨╛╨│╨╗╨░╤Б╨╕╨╡.");
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
        granted: "╨╡╤Б╤В╤М ╤Б╨╛╨│╨╗╨░╤Б╨╕╨╡",
        denied: "╨╛╤В╨║╨░╨╖",
        revoked: "╨╛╤В╨╛╨╖╨▓╨░╨╜╨╛",
        none: "╨╜╨╡╤В ╤Б╨╛╨│╨╗╨░╤Б╨╕╤П",
      };
      setMarketingConsentLabel(map[st] || st);
    } catch {
      setMarketingConsentLabel("╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛");
    }
  }

  async function requestMarketingConsent() {
    if (!token || !detail) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/marketing-consent/request`, token, {
        method: "POST",
      });
      setNotice("╨Ч╨░╨┐╤А╨╛╤Б ╤Б╨╛╨│╨╗╨░╤Б╨╕╤П ╨╜╨░ ╤А╨░╤Б╤Б╤Л╨╗╨║╤Г ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜ ╨▓ MAX.");
      await loadMarketingConsent(detail.id);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╖╨░╨┐╤А╨╛╤Б╨╕╤В╤М ╤Б╨╛╨│╨╗╨░╤Б╨╕╨╡ ╨╜╨░ ╤А╨░╤Б╤Б╤Л╨╗╨║╤Г.",
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
      if (result.ok) setNotice("╨Я╨╕╤Б╤М╨╝╨╛ ┬л╨╖╨░╨┐╤А╨╛╤Б ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓┬╗ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨╛.");
      else if (result.skipped) setNotice("╨Я╨╛╤З╤В╨░ ╨┐╤А╨╛╨┐╤Г╤Й╨╡╨╜╨░ (╨╜╨╡╤В ╤В╨╛╨║╨╡╨╜╨░ / ╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨░).");
      else setNotice(`╨Я╨╛╤З╤В╨░: ${result.error || "╨╛╤И╨╕╨▒╨║╨░"}`);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨╖╨░╨┐╤А╨╛╤Б ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓.");
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
      setNotice(isTest ? "╨Я╨╛╨╝╨╡╤З╨╡╨╜╨╛ ╨║╨░╨║ ╤В╨╡╤Б╤В╨╛╨▓╨╛╨╡." : "╨г╨▒╤А╨░╨╜╨╛ ╨╕╨╖ ╤В╨╡╤Б╤В╨╛╨▓╤Л╤Е.");
      await loadCases();
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╨▒╨╜╨╛╨▓╨╕╤В╤М ╤Д╨╗╨░╨│. ╨Э╤Г╨╢╨╜╨░ ╤А╨╛╨╗╤М ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░ ╨╕ ╨╝╨╕╨│╤А╨░╤Ж╨╕╤П is_test.");
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
      setNotice("╨б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╣ ╤И╨░╨│ ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜.");
      await openCase(detail.id);
      await loadDashboard();
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╣ ╤И╨░╨│. ╨Х╤Б╨╗╨╕ ╨║╨╛╨╗╨╛╨╜╨║╨╕ ╨╡╤Й╤С ╨╜╨╡ ╨┐╤А╨╕╨╝╨╡╨╜╨╡╨╜╤Л ╨▓ ╨С╨Ф тАФ ╨┐╤А╨╕╨╝╨╡╨╜╨╕╤В╨╡ ╨╝╨╕╨│╤А╨░╤Ж╨╕╤О.");
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
      setNotice("╨Р╤А╤Е╨╕╨▓╨╜╤Л╨╣ ╨▒╨╗╨╛╨║ ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜.");
      await openCase(detail.id);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╨░╤А╤Е╨╕╨▓╨╜╤Л╨╣ ╨▒╨╗╨╛╨║. ╨Э╤Г╨╢╨╜╨░ ╨╝╨╕╨│╤А╨░╤Ж╨╕╤П cases_archive_prep.");
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
          ? `╨Ю╤В╨║╨░╨╖ ╨╖╨░╤Д╨╕╨║╤Б╨╕╤А╨╛╨▓╨░╨╜: ${payload.loss_reason || "тАФ"}`
          : "╨Ф╨╡╨╗╨╛ ╨╖╨░╨║╤А╤Л╤В╨╛ ╤Г╤Б╨┐╨╡╤И╨╜╨╛.",
      );
      await openCase(detail.id);
      await loadDashboard();
      await loadCases();
    } catch {
      setNotice(
        "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╖╨░╨║╤А╤Л╤В╤М ╨┤╨╡╨╗╨╛. ╨Я╤А╨╛╨▓╨╡╤А╤М╤В╨╡ ╨┐╤А╨╕╤З╨╕╨╜╤Г ╨╛╤В╨║╨░╨╖╨░ ╨╕╨╗╨╕ ╨┐╤А╨╕╨╝╨╡╨╜╨╕╤В╨╡ ╨╝╨╕╨│╤А╨░╤Ж╨╕╤О loss_reason.",
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
    setNotice("╨н╤В╨░╨┐ ╨╛╨▒╨╜╨╛╨▓╨╗╤С╨╜.");
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
    setNotice("╨а╨╡╨╖╤Г╨╗╤М╤В╨░╤В ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╤С╨╜, ╨╖╨░╨┐╨╕╤Б╤М ╨▓ audit.");
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
      setNotice("╨б╤З╤С╤В ╤Б╨╛╨╖╨┤╨░╨╜.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╨╖╨┤╨░╤В╤М ╤Б╤З╤С╤В.");
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
      setNotice("╨з╨╡╤А╨╜╨╛╨▓╨╕╨║ ╤Б╤З╤С╤В╨░ ╤Б╨╛╨╖╨┤╨░╨╜.");
      await loadFinance(financeQueue);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╨╖╨┤╨░╤В╤М ╤Б╤З╤С╤В.");
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
      if (!url) throw new Error("╨Э╨╡╤В ╤Б╤Б╤Л╨╗╨║╨╕");
      await navigator.clipboard.writeText(url);
      setNotice("╨Ъ╨╛╤А╨╛╤В╨║╨░╤П ╤Б╤Б╤Л╨╗╨║╨░ ╨оKassa ╤Б╨║╨╛╨┐╨╕╤А╨╛╨▓╨░╨╜╨░. QR тАФ ╨▓ ╨║╨░╤А╤В╨╛╤З╨║╨╡ ╤Б╤З╤С╤В╨░.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╤Б╤Б╤Л╨╗╨║╤Г ╨╜╨░ ╨╛╨┐╨╗╨░╤В╤Г.");
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
      setNotice(result.sent ? "╨б╤Б╤Л╨╗╨║╨░ ╨╕ QR ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╤Л ╨║╨╗╨╕╨╡╨╜╤В╤Г ╨▓ MAX." : "╨б╤Б╤Л╨╗╨║╨░ ╤Б╨╛╨╖╨┤╨░╨╜╨░, MAX ╨╜╨╡ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜.");
      await loadFinance(financeQueue);
      if (detail && String(order.case_id) === detail.id) {
        await openCase(detail.id);
        const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
        setMessages(next);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╤Б╤Б╤Л╨╗╨║╤Г ╨▓ MAX.");
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
          ? "╨б╤З╤С╤В ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜ ╨▓ MAX тАФ ╤В╨╡╨║╤Б╤В, ╨║╨╜╨╛╨┐╨║╨░ ╨╕ QR ╨┐╨╛╤П╨▓╤П╤В╤Б╤П ╨▓ ╨╗╨╡╨╜╤В╨╡ ╤З╨░╤В╨░."
          : "╨б╤Б╤Л╨╗╨║╨░ ╤Б╨╛╨╖╨┤╨░╨╜╨░, ╨╜╨╛ MAX ╨╜╨╡ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜ (╨┐╤А╨╛╨▓╨╡╤А╤М╤В╨╡ ╨┐╤А╨╕╨▓╤П╨╖╨║╤Г ╨║╨╗╨╕╨╡╨╜╤В╨░).",
      );
      await openCase(detail.id);
      const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
      setMessages(next);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╤Б╤З╤С╤В ╨▓ MAX.");
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
      if (!url) throw new Error("╨Э╨╡╤В ╤Б╤Б╤Л╨╗╨║╨╕");
      await navigator.clipboard.writeText(url);
      setNotice("╨б╤Б╤Л╨╗╨║╨░ ╤Б╨║╨╛╨┐╨╕╤А╨╛╨▓╨░╨╜╨░. QR ╨┐╨╛╤П╨▓╨╕╤В╤Б╤П ╨▓ ╨▒╨╗╨╛╨║╨╡ ╨╛╨┐╨╗╨░╤В╤Л ╨┤╨╡╨╗╨░.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╤Б╤Б╤Л╨╗╨║╤Г.");
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
      setNotice(result.sent ? "╨Э╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╨╡ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨╛ ╨▓ MAX." : "╨з╨╡╤А╨╜╨╛╨▓╨╕╨║ ╨╜╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╤П ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨┤╨│╨╛╤В╨╛╨▓╨╕╤В╤М ╨╜╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╨╡.");
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
      setNotice("╨Ю╨┐╨╗╨░╤В╨░ ╨╛╤В╨╝╨╡╤З╨╡╨╜╨░, ╨╖╨░╨┐╨╕╤Б╤М ╨▓ ╨╢╤Г╤А╨╜╨░╨╗╨╡ ╨░╤Г╨┤╨╕╤В╨░.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨╝╨╡╤В╨╕╤В╤М ╨╛╨┐╨╗╨░╤В╤Г.");
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
      setNotice("╨б╤З╤С╤В ╨╛╤В╨╝╨╡╨╜╤С╨╜.");
      await loadFinance(financeQueue);
    } catch {
      setNotice("╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨╝╨╡╨╜╨╕╤В╤М ╤Б╤З╤С╤В.");
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
    setNotice(`╨Ю╨▒╤А╨░╤В╨╜╨░╤П ╤Б╨▓╤П╨╖╤М ╨┤╨╗╤П ╨▒╨░╨╖╤Л ╨╖╨╜╨░╨╜╨╕╨╣ ╤Б╨╛╤Е╤А╨░╨╜╨╡╨╜╨░ (${labelFeedbackQuality(feedbackQuality)}).`);
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
        setNotice("DeepSeek ╨╜╨╡ ╨▓╨╡╤А╨╜╤Г╨╗ ╨▓╨░╤А╨╕╨░╨╜╤В╤Л тАФ ╨┐╤А╨╛╨▓╨╡╤А╤М╤В╨╡ ╨║╨╗╤О╤З Yandex AI Studio.");
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╨┐╨╛╨┤╤Б╨║╨░╨╖╨║╨╕.");
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
      setNotice("╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨╛ ╨║╨╗╨╕╨╡╨╜╤В╤Г ╨▓ MAX.");
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
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨▓ MAX.");
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
        body: JSON.stringify({ body: maxReplyBody.trim(), internal: true }),
    });
      setMaxReplyBody("");
    const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
    setMessages(next);
      setNotice("╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╤Б╨╛╤Е╤А╨░╨╜╨╡╨╜╨╛ ╨▓ ╨╗╨╡╨╜╤В╤Г ╨┤╨╡╨╗╨░.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡.");
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
      setNotice("╨Я╤А╨╡╨┤╤Б╤В╨░╨▓╨╕╤В╨╡╨╗╤М ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┤╨╛╨▒╨░╨▓╨╕╤В╤М ╨┐╤А╨╡╨┤╤Б╤В╨░╨▓╨╕╤В╨╡╨╗╤П.");
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
      setNotice("╨Ф╨╛╤Б╤В╤Г╨┐ ╨┐╤А╨╡╨┤╤Б╤В╨░╨▓╨╕╤В╨╡╨╗╤П ╤Б╨╜╤П╤В.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╜╤П╤В╤М ╨┤╨╛╤Б╤В╤Г╨┐.");
    }
  }

  async function openSigned(docId: string) {
    if (!token || !detail) return;
    const signed = await apiFetch<{ url: string; expires_in: number }>(
      `/api/portal/cases/${detail.id}/documents/${docId}/signed-url`,
      token,
      { method: "POST" },
    );
    const link = document.createElement("a");
    link.href = signed.url;
    link.rel = "noopener noreferrer";
    link.download = "";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setNotice(`╨б╨║╨░╤З╨╕╨▓╨░╨╜╨╕╨╡ ╨╜╨░╤З╨░╤В╨╛. ╨б╤Б╤Л╨╗╨║╨░ ╨┤╨╡╨╣╤Б╤В╨▓╤Г╨╡╤В ${signed.expires_in} ╤Б╨╡╨║.`);
  }

  async function uploadDiagnosisReport(file: File) {
    if (!token || !detail) return;
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setNotice("╨Э╤Г╨╢╨╡╨╜ PDF ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨░ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕.");
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
      setNotice("PDF ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨░ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕ ╨╖╨░╨│╤А╤Г╨╢╨╡╨╜ ╨▓ ╨║╨░╨▒╨╕╨╜╨╡╤В.");
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╖╨░╨│╤А╤Г╨╖╨╕╤В╤М PDF.");
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
      let msg = `╨Ю╨┐╤Г╨▒╨╗╨╕╨║╨╛╨▓╨░╨╜╨╛. ╨з╨╡╤А╨╜╨╛╨▓╨╕╨║╨╛╨▓ ╤Г╨▓╨╡╨┤╨╛╨╝╨╗╨╡╨╜╨╕╨╣: ${n}.`;
      if (out.share_url_once) {
        try {
          await navigator.clipboard.writeText(out.share_url_once);
          msg += " ╨б╤Б╤Л╨╗╨║╨░ ╤Б╨║╨╛╨┐╨╕╤А╨╛╨▓╨░╨╜╨░ ╨▓ ╨▒╤Г╤Д╨╡╤А (╨╛╨┤╨╕╨╜ ╤А╨░╨╖).";
        } catch {
          msg += " ╨б╤Б╤Л╨╗╨║╨░ ╨▓ ╨╛╤В╨▓╨╡╤В╨╡ API (╨╛╨┤╨╕╨╜ ╤А╨░╨╖).";
        }
      }
      setNotice(msg);
      await openCase(detail.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╨┐╤Г╨▒╨╗╨╕╨║╨╛╨▓╨░╤В╤М.");
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
                alt="╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤Б╤В╨░╨╢╨░"
              />
              ╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤Б╤В╨░╨╢╨░ ┬╖ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨╕
            </BrandHomeLink>
          </p>
          <h1>╨Ъ╨░╨▒╨╕╨╜╨╡╤В ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░</h1>

          <div className="auth-tabs" role="tablist" aria-label="╨Т╤Е╨╛╨┤ ╨╕╨╗╨╕ ╨╖╨░╤П╨▓╨║╨░ ╨╜╨░ ╨┤╨╛╤Б╤В╤Г╨┐">
            <button
              type="button"
              role="tab"
              id="auth-tab-login"
              aria-selected={loginTabActive}
              className={loginTabActive ? "auth-tab active" : "auth-tab"}
              onClick={() => goAuthScreen("max")}
            >
              ╨Т╤Е╨╛╨┤
            </button>
            <button
              type="button"
              role="tab"
              id="auth-tab-register"
              aria-selected={!loginTabActive}
              className={!loginTabActive ? "auth-tab active" : "auth-tab"}
              onClick={() => goAuthScreen("register")}
            >
              ╨Ч╨░╨┐╤А╨╛╤Б ╨┤╨╛╤Б╤В╤Г╨┐╨░
            </button>
          </div>

          {authScreen === "max" ? (
            <>
              <p className="lead lead-compact">
                ╨Т╤Е╨╛╨┤ ╤З╨╡╤А╨╡╨╖ ops-╨▒╨╛╤В MAX ┬л╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤Б╤В╨░╨╢╨░-Ops┬╗: ╨┐╨╛╨╗╤Г╤З╨╕╤В╨╡ ╨║╨╛╨┤ ╨╜╨░ ╤Н╤В╨╛╨╣ ╤Б╤В╤А╨░╨╜╨╕╤Ж╨╡,
                ╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╨╡ ╨▓ MAX. ╨Ф╨╛╤Б╤В╤Г╨┐ ╨╛╤В╨║╤А╤Л╨▓╨░╨╡╤В╤Б╤П ╨┐╨╛╤Б╨╗╨╡ ╨╛╨┤╨╛╨▒╤А╨╡╨╜╨╕╤П ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝.
              </p>
              <label htmlFor="email-max">╨а╨░╨▒╨╛╤З╨╕╨╣ email</label>
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
                      ╨Я╨╛╨╗╤Г╤З╨╕╤В╤М ╨║╨╛╨┤
                    </button>
                    <ol className="max-login-steps">
                      <li>╨Э╨░╨╢╨╝╨╕╤В╨╡ ┬л╨Я╨╛╨╗╤Г╤З╨╕╤В╤М ╨║╨╛╨┤┬╗ тАФ ╨┐╨╛╤П╨▓╤П╤В╤Б╤П 6 ╤Ж╨╕╤Д╤А</li>
                      <li>╨Э╨░╨╢╨╝╨╕╤В╨╡ ┬л╨Я╨╡╤А╨╡╨╣╤В╨╕ ╨▓ MAX┬╗</li>
                      <li>╨Т ops-╨▒╨╛╤В╨╡ ╨╛╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╨║╨╛╨┤ ╨╕ ╨╜╨░╨╢╨╝╨╕╤В╨╡ ┬л╨Т╨╛╨╣╤В╨╕ ╨▓ ╨║╨░╨▒╨╕╨╜╨╡╤В ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░┬╗</li>
                    </ol>
                  </>
                ) : (
                  <>
                    <p className="max-wizard-status" role="status">
                      {maxWaitStatus === "pending_manager"
                        ? "╨Ъ╨╛╨┤ ╨┐╤А╨╕╨╜╤П╤В. ╨Ц╨┤╤С╨╝ ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤П ╨▓ ╤З╨░╤В╨╡ MAXтАж"
                        : maxWaitStatus === "pending_confirm"
                          ? "╨Я╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╨▓ ops-╨▒╨╛╤В╨╡ тАФ ╨║╨░╨▒╨╕╨╜╨╡╤В ╨╛╤В╨║╤А╨╛╨╡╤В╤Б╤П ╨╖╨┤╨╡╤Б╤М"
                          : maxPairCode
                            ? "╨Ю╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╨║╨╛╨┤ ╨▓ ops-╨▒╨╛╤В MAX"
                            : "╨Я╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╨▓ ops-╨▒╨╛╤В╨╡ MAX"}
                    </p>
                    {maxPairCode ? (
                      <p className="max-code-block">
                        ╨Ъ╨╛╨┤: <strong className="max-pair-code">{maxPairCode}</strong>
                      </p>
                    ) : null}
                    <button
                      type="button"
                      className="max-action-btn"
                      onClick={openMaxChat}
                    >
                      ╨Я╨╡╤А╨╡╨╣╤В╨╕ ╨▓ MAX
                    </button>
                    <ol className="max-login-steps">
                      <li>╨Ю╤В╨║╤А╨╛╨╣╤В╨╡ ops-╨▒╨╛╤В ┬л╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤Б╤В╨░╨╢╨░-Ops┬╗</li>
                      {maxPairCode ? (
                        <>
                          <li>╨Ю╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╨║╨╛╨┤ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡╨╝ ╨▓ ╤З╨░╤В</li>
                          <li>╨Э╨░╨╢╨╝╨╕╤В╨╡ ┬л╨Т╨╛╨╣╤В╨╕ ╨▓ ╨║╨░╨▒╨╕╨╜╨╡╤В ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░┬╗</li>
                        </>
                      ) : (
                        <li>╨Э╨░╨╢╨╝╨╕╤В╨╡ ┬л╨Т╨╛╨╣╤В╨╕ ╨▓ ╨║╨░╨▒╨╕╨╜╨╡╤В ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░┬╗</li>
                      )}
                    </ol>
                    {maxWaitStatus === "pending_manager" ? (
                      <p className="hint">
                        ╨а╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤М ╨╜╨░╨╢╨╝╤С╤В ┬л╨а╨░╨╖╤А╨╡╤И╨╕╤В╤М ╨▓╤Е╨╛╨┤┬╗ тАФ ╨║╨░╨▒╨╕╨╜╨╡╤В ╨╛╤В╨║╤А╨╛╨╡╤В╤Б╤П ╤Б╨░╨╝.
                      </p>
                    ) : (
                      <p className="hint">
                        ╨Я╨╛╤Б╨╗╨╡ ╨║╨╜╨╛╨┐╨║╨╕ ╨▓ ops-╨▒╨╛╤В╨╡ ╨║╨░╨▒╨╕╨╜╨╡╤В ╨╛╤В╨║╤А╨╛╨╡╤В╤Б╤П ╨╜╨░ ╤Н╤В╨╛╨╣ ╤Б╤В╤А╨░╨╜╨╕╤Ж╨╡.
                      </p>
                    )}
                    <button type="button" className="ghost" onClick={resetMaxWizard}>
                      ╨Э╨░╤З╨░╤В╤М ╨╖╨░╨╜╨╛╨▓╨╛
                    </button>
                  </>
                )}
              </div>
              <div className="auth-alt-hint">
                <p className="auth-alt-label">╨Ф╤А╤Г╨│╨╕╨╡ ╤Б╨┐╨╛╤Б╨╛╨▒╤Л ╨▓╤Е╨╛╨┤╨░</p>
                <div className="auth-alt-list" role="group" aria-label="╨Ф╤А╤Г╨│╨╕╨╡ ╤Б╨┐╨╛╤Б╨╛╨▒╤Л ╨▓╤Е╨╛╨┤╨░">
                  <button
                    type="button"
                    className="auth-alt-btn"
                    onClick={() => goAuthScreen("email_otp")}
                  >
                    ╨Ъ╨╛╨┤ ╨╜╨░ ╤А╨░╨▒╨╛╤З╤Г╤О ╨┐╨╛╤З╤В╤Г
                  </button>
                </div>
              </div>
            </>
          ) : null}

          {authScreen === "email_otp" ? (
            <>
              {!otpSent ? (
                <form className="auth-form" onSubmit={signIn}>
                  <label htmlFor="email">╨а╨░╨▒╨╛╤З╨╕╨╣ email</label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                  <button type="submit" disabled={busy}>
                    ╨Я╨╛╨╗╤Г╤З╨╕╤В╤М ╨║╨╛╨┤
                  </button>
                </form>
              ) : (
                <form className="auth-form" onSubmit={verifyOtp}>
                  <label htmlFor="otp">╨Ъ╨╛╨┤ ╤Б ╨┐╨╛╤З╤В╤Л</label>
                  <input
                    id="otp"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    required
                    inputMode="numeric"
                    autoComplete="one-time-code"
                  />
                  <button type="submit">╨Т╨╛╨╣╤В╨╕</button>
                </form>
              )}
              <p className="hint">
                <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                  тЖР ╨Т╨╛╨╣╤В╨╕ ╤З╨╡╤А╨╡╨╖ MAX
                </button>
              </p>
            </>
          ) : null}

          {authScreen === "register" ? (
            <>
              <p className="lead lead-compact">
                ╨Ч╨░╨┐╨╛╨╗╨╜╨╕╤В╨╡ ╨╖╨░╤П╨▓╨║╤Г тАФ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А ╨┐╨╛╨╗╤Г╤З╨╕╤В ╨┐╨╕╤Б╤М╨╝╨╛ ╨╜╨░{" "}
                <strong>proverkastaza@yandex.ru</strong> ╨╕ ╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В ╨┤╨╛╤Б╤В╤Г╨┐. ╨Я╨╛╤Б╨╗╨╡ ╨╛╨┤╨╛╨▒╤А╨╡╨╜╨╕╤П
                ╨┐╤А╨╕╨┤╤С╤В ╨┐╤А╨╕╨│╨╗╨░╤И╨╡╨╜╨╕╨╡ ╨╜╨░ ╨▓╨░╤И e-mail.
              </p>
              {registerSent ? (
                <p className="notice" role="status">
                  {notice ||
                    "╨Ч╨░╤П╨▓╨║╨░ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨░. ╨Ф╨╛╨╢╨┤╨╕╤В╨╡╤Б╤М ╨┐╨╕╤Б╤М╨╝╨░ ╤Б ╨┤╨╛╤Б╤В╤Г╨┐╨╛╨╝ ╨┐╨╛╤Б╨╗╨╡ ╨╛╨┤╨╛╨▒╤А╨╡╨╜╨╕╤П ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝."}
                </p>
              ) : (
                <form className="auth-form" onSubmit={requestStaffRegister}>
                  <label htmlFor="reg-name">╨Ш╨╝╤П ╨╕ ╤Д╨░╨╝╨╕╨╗╨╕╤П</label>
                  <input
                    id="reg-name"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    autoComplete="name"
                    required
                  />
                  <label htmlFor="reg-email">╨а╨░╨▒╨╛╤З╨╕╨╣ e-mail</label>
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
                      ╨б╨╛╨│╨╗╨░╤Б╨╡╨╜ ╤Б{" "}
                      <a href={`${SITE_URL}/soglasie/`} target="_blank" rel="noopener noreferrer">
                        ╨б╨Ю╨Я╨Ф
                      </a>{" "}
                      ╨┤╨╗╤П ╤А╨░╤Б╤Б╨╝╨╛╤В╤А╨╡╨╜╨╕╤П ╨╖╨░╤П╨▓╨║╨╕
                    </span>
                  </label>
                  <button type="submit" disabled={busy || !registerConsent}>
                    ╨Ю╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨╖╨░╤П╨▓╨║╤Г
                  </button>
                  {notice ? <p className="notice">{notice}</p> : null}
                </form>
              )}
              {!registerSent ? (
                <p className="hint">
                  <button type="button" className="linkish" onClick={() => goAuthScreen("max")}>
                    тЖР ╨г╨╢╨╡ ╨╡╤Б╤В╤М ╨┤╨╛╤Б╤В╤Г╨┐ тАФ ╨▓╨╛╨╣╤В╨╕
                  </button>
                </p>
              ) : null}
            </>
          ) : null}

          {authScreen !== "register" && notice ? <p className="notice">{notice}</p> : null}
          {authScreen !== "register" ? (
            <p className="hint auth-staff-hint">
              ╨Э╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐╨░? ╨Т╨║╨╗╨░╨┤╨║╨░ ┬л╨Ч╨░╨┐╤А╨╛╤Б ╨┤╨╛╤Б╤В╤Г╨┐╨░┬╗ ╨╕╨╗╨╕ ╨┐╨╛╨┐╤А╨╛╤Б╨╕╤В╨╡ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░ ╨┤╨╛╨▒╨░╨▓╨╕╤В╤М ╨▓╨░╤Б ╨▓ ╤А╨░╨╖╨┤╨╡╨╗╨╡ ┬л╨а╨╛╨╗╨╕┬╗.
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
            <h1>╨Э╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐╨░</h1>
            <p className="lead lead-compact">
              ╨Т╤Е╨╛╨┤ ╨▓╤Л╨┐╨╛╨╗╨╜╨╡╨╜, ╨╜╨╛ ╤А╨╛╨╗╨╕ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ╨╜╨╡╤В. ╨Я╨╛╨┐╤А╨╛╤Б╨╕╤В╨╡ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░ ╨┤╨╛╨▒╨░╨▓╨╕╤В╤М ╨▓╨░╤Б ╨▓ ╤А╨░╨╖╨┤╨╡╨╗╨╡
              ┬л╨а╨╛╨╗╨╕┬╗ тАФ ╨╛╤В╨║╤А╤Л╤В╨╛╨╣ ╤А╨╡╨│╨╕╤Б╤В╤А╨░╤Ж╨╕╨╕ ╨╜╨╡╤В.
            </p>
            <button type="button" className="max-action-btn" onClick={() => void supabase?.auth.signOut()}>
              ╨Т╤Л╨╣╤В╨╕
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
              alt="╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤Б╤В╨░╨╢╨░"
            />
            <div>
              <strong>╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤Б╤В╨░╨╢╨░</strong>
              <span>
                ╨Ъ╨░╨▒╨╕╨╜╨╡╤В ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ┬╖ {me?.role ? labelStaffRole(me.role) : "тАж"} ┬╖ {me?.email ?? ""}
              </span>
            </div>
          </BrandHomeLink>
        </div>
        <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
          ╨Т╤Л╨╣╤В╨╕
        </button>
      </header>

      <section className="warning" role="note">
        ╨а╨╡╤И╨╡╨╜╨╕╨╡ ╨┐╤А╨╕╨╜╨╕╨╝╨░╨╡╤В ╨б╨д╨а. ╨а╨╡╨╖╤Г╨╗╤М╤В╨░╤В ╨╜╨╡ ╨│╨░╤А╨░╨╜╤В╨╕╤А╨╛╨▓╨░╨╜. ╨д╤Г╨╜╨║╤Ж╨╕╨╕ ╨║╨░╨▒╨╕╨╜╨╡╤В╨░ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ╨╜╨╡ ╨┐╨╡╤А╨╡╨╜╨╛╤Б╤П╤В╤Б╤П ╨▓ ╨╝╨╕╨╜╨╕-╨┐╤А╨╕╨╗╨╛╨╢╨╡╨╜╨╕╨╡ MAX (╨в╨Ч-09).
      </section>

      <nav className="tabs" aria-label="╨а╨░╨╖╨┤╨╡╨╗╤Л">
        <button type="button" className={view === "dashboard" ? "tab active" : "tab"} onClick={() => { setView("dashboard"); void loadDashboard(); }}>
          ╨Ф╨░╤И╨▒╨╛╤А╨┤
        </button>
        <button type="button" className={view === "cases" || view === "case" ? "tab active" : "tab"} onClick={() => { setView("cases"); void loadCases(); }}>
          ╨а╨╡╨╡╤Б╤В╤А ╨┤╨╡╨╗
        </button>
        {me?.role !== "operator" && (
          <button type="button" className={view === "finance" ? "tab active" : "tab"} onClick={() => void loadFinance()}>
            ╨д╨╕╨╜╨░╨╜╤Б╤Л
          </button>
        )}
        {(me?.role === "admin" || me?.role === "expert" || me?.role_capabilities?.can_view_analytics) && (
          <button type="button" className={view === "analytics" ? "tab active" : "tab"} onClick={() => void loadAnalytics()}>
            ╨Р╨╜╨░╨╗╨╕╤В╨╕╨║╨░
          </button>
        )}
        {(me?.role === "admin" || me?.role_capabilities?.can_manage_roles) && (
          <button type="button" className={view === "roles" ? "tab active" : "tab"} onClick={() => void loadRoles()}>
            ╨а╨╛╨╗╨╕
          </button>
        )}
      </nav>

      {notice && (
        <p
          className={`notice notice--sticky${/╨╜╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М|╨╛╤И╨╕╨▒╨║/i.test(notice) ? " notice--error" : ""}`}
          role="status"
        >
          {notice}
        </p>
      )}

      {view === "dashboard" && dashboard && (
        <section className="stack">
          <h1>╨Ф╨░╤И╨▒╨╛╤А╨┤</h1>
          <p className="lead lead-compact">
            ╨б╨╡╨│╨╛╨┤╨╜╤П: <strong>{dashboard.greeting_priority_count}</strong>{" "}
            {dashboard.greeting_priority_count === 1 ? "╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╡" : "╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╣"} ╤Б ╨▓╤Л╤Б╨╛╨║╨╕╨╝ ╨┐╤А╨╕╨╛╤А╨╕╤В╨╡╤В╨╛╨╝.
            ╨б╨╜╨░╤З╨░╨╗╨░ ╨╛╤В╨▓╨╡╤З╨░╨╡╨╝ ╨║╨╗╨╕╨╡╨╜╤В╤Г, ╨╖╨░╤В╨╡╨╝ ╨╖╨░╨║╤А╤Л╨▓╨░╨╡╨╝ ╨┤╨╡╨┤╨╗╨░╨╣╨╜╤Л ╨╕ ╤А╨╕╤Б╨║╨╕ SLA.
          </p>
          <div className="metrics">
            <button type="button" className="metric-card" onClick={() => setQueueFilter("reply")}>
              <span>╨в╤А╨╡╨▒╤Г╤О╤В ╨╝╨╛╨╡╨│╨╛ ╨╛╤В╨▓╨╡╤В╨░</span>
              <strong>{dashboard.needs_reply}</strong>
              <em>{dashboard.needs_reply_over_30m} ╨▒╨╡╨╖ ╨╛╤В╨▓╨╡╤В╨░ ╨▒╨╛╨╗╨╡╨╡ 30 ╨╝╨╕╨╜</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("today")}>
              <span>╨Ф╨╡╨┤╨╗╨░╨╣╨╜ ╤Б╨╡╨│╨╛╨┤╨╜╤П</span>
              <strong>{dashboard.deadline_today}</strong>
              <em>╨Ч╨░╨┤╨░╤З╨╕ ╨╕ ╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╣ ╤И╨░╨│ ╨╜╨░ ╤Б╨╡╨│╨╛╨┤╨╜╤П</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("new")}>
              <span>╨Э╨╛╨▓╤Л╨╡ ╨╛╨▒╤А╨░╤Й╨╡╨╜╨╕╤П</span>
              <strong>{dashboard.new_leads}</strong>
              <em>╨Ч╨░╤П╨▓╨║╨╕ ╨▒╨╡╨╖ ╨┐╨╡╤А╨╡╨▓╨╛╨┤╨░ ╨▓ ╤А╨░╨▒╨╛╤В╤Г</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("docs")}>
              <span>╨Ю╨╢╨╕╨┤╨░╨╡╨╝ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л</span>
              <strong>{dashboard.waiting_docs}</strong>
              <em>
                {dashboard.waiting_docs_max_days > 0
                  ? `╤Б╨░╨╝╨╛╨╡ ╨┤╨╛╨╗╨│╨╛╨╡ ╨╛╨╢╨╕╨┤╨░╨╜╨╕╨╡ ${dashboard.waiting_docs_max_days} ╨┤╨╜.`
                  : "╨Ш╨Ы╨б, ╤В╤А╤Г╨┤╨╛╨▓╨░╤П, ╤Б╨┐╤А╨░╨▓╨║╨╕, ╤Б╨╛╨│╨╗╨░╤Б╨╕╨╡"}
              </em>
            </button>
            <button type="button" className="metric-card" onClick={() => void loadFinance({ queue: "payable" })}>
              <span>╨Ю╨╢╨╕╨┤╨░╨╡╨╝ ╨╛╨┐╨╗╨░╤В╤Г</span>
              <strong>{dashboard.payments_pending} / {formatRub(dashboard.payments_pending_amount)}</strong>
              <em>
                ╨Ю╨┐╨╗╨░╤З╨╡╨╜╨╛ ╤Б╨╡╨│╨╛╨┤╨╜╤П: {dashboard.payments_paid_today} / {formatRub(dashboard.payments_paid_today_amount)}
                {" ┬╖ "}╤Б╤З╨╡╤В╨░ ╨╜╨░ ╨▓╨║╨╗╨░╨┤╨║╨╡ ╨д╨╕╨╜╨░╨╜╤Б╤Л
              </em>
            </button>
            <button type="button" className={`metric-card ${dashboard.sla_risk > 0 ? "metric-card--risk" : ""}`} onClick={() => setQueueFilter("sla")}>
              <span>╨а╨╕╤Б╨║ SLA</span>
              <strong>{dashboard.sla_risk}</strong>
              <em>╨б╤А╨╛╨║ ╨╛╤В╨▓╨╡╤В╨░ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ╨╜╨░╤А╤Г╤И╨╡╨╜</em>
            </button>
            <button type="button" className="metric-card" onClick={() => setQueueFilter("conflicts")}>
              <span>╨Ъ╨╛╨╜╤Д╨╗╨╕╨║╤В╤Л ╨║╨░╨╜╨░╨╗╨╛╨▓</span>
              <strong>{dashboard.channel_conflicts}</strong>
              <em>╨Я╤А╨╡╨┤╨┐╨╛╤З╤В╨╡╨╜╨╕╨╡ MAX/╨▓╨╡╨▒ ╨▒╨╡╨╖ ╨┐╤А╨╕╨▓╤П╨╖╨║╨╕. ╨С╨╡╨╖ MAX / ╨▒╨╡╨╖ ╨▓╨╡╨▒: {dashboard.unlinked_max} / {dashboard.unlinked_web}</em>
            </button>
          </div>

          <div className="dashboard-split">
            <div className="panel">
              <h2>╨Ь╨╛╨╕ ╨╖╨░╨┤╨░╤З╨╕ ╤Б╨╡╨│╨╛╨┤╨╜╤П</h2>
              {dashboard.my_tasks_today.length === 0 ? (
                <p className="hint">╨б╤А╨╛╤З╨╜╤Л╤Е ╨╖╨░╨┤╨░╤З ╨╜╨╡╤В тАФ ╨╝╨╛╨╢╨╜╨╛ ╤А╨░╨╖╨╛╨▒╤А╨░╤В╤М ╤Б╤В╨░╨╜╨┤╨░╤А╤В╨╜╤Г╤О ╨╛╤З╨╡╤А╨╡╨┤╤М.</p>
              ) : (
                <ul className="plain-list task-list">
                  {dashboard.my_tasks_today.map((item) => (
                    <li key={item.case_id}>
                      <button type="button" className="linkish" onClick={() => void openCase(item.case_id)}>
                        <strong>{formatWhen(item.next_action_at)}</strong>
                        {" ┬╖ "}
                        {item.client_name ?? "╨Ъ╨╗╨╕╨╡╨╜╤В"} тАФ {item.next_action}
                </button>
              </li>
            ))}
          </ul>
              )}
            </div>
            <div className="panel">
              <h2>╨Ъ╨╛╨╜╤В╤А╨╛╨╗╤М ╤Б╤А╨╛╨║╨╛╨▓ ╨╛╤В╨▓╨╡╤В╨░</h2>
              <p className="hint">╨Ю╨╢╨╕╨┤╨░╨╜╨╕╨╡ ╨░╤А╤Е╨╕╨▓╨░, ╨б╨д╨а ╨╕╨╗╨╕ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓ ╨║╨╗╨╕╨╡╨╜╤В╨░ ╨╜╨╡ ╤Б╤З╨╕╤В╨░╨╡╤В╤Б╤П ┬л╨▒╨╡╨╖ ╨╛╤В╨▓╨╡╤В╨░┬╗.</p>
              <ul className="plain-list sla-list">
                <li className="tone-risk">╨Я╤А╨╛╤Б╤А╨╛╤З╨╡╨╜╨╛: {dashboard.sla_control.overdue ?? 0}</li>
                <li className="tone-warn">╨Ю╤В╨▓╨╡╤В ╨╜╤Г╨╢╨╡╨╜ ╨▓ 1 ╤З╨░╤Б: {dashboard.sla_control.due_1h ?? 0}</li>
                <li className="tone-today">╨Ю╤В╨▓╨╡╤В ╨╜╤Г╨╢╨╡╨╜ ╤Б╨╡╨│╨╛╨┤╨╜╤П: {dashboard.sla_control.due_today ?? 0}</li>
                <li className="tone-wait">╨Ю╨╢╨╕╨┤╨░╨╡╨╝ ╨║╨╗╨╕╨╡╨╜╤В╨░ / ╨░╤А╤Е╨╕╨▓ / ╨б╨д╨а: {dashboard.sla_control.waiting_external ?? 0}</li>
                <li className="tone-muted">╨Э╨░ ╨┐╨░╤Г╨╖╨╡: {dashboard.sla_control.paused ?? 0}</li>
              </ul>
            </div>
          </div>

          <div className="panel">
            <h2>╨б╤В╨░╤В╤Г╤Б ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓</h2>
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
                    {label} тАФ {count}
                </button>
                );
              })}
            </div>
          </div>

          <div className="panel">
            <h2>╨а╨░╨▒╨╛╤З╨░╤П ╨╛╤З╨╡╤А╨╡╨┤╤М</h2>
            <div className="chip-row">
              {[
                ["all", "╨Т╤Б╨╡"],
                ["urgent", "╨б╤А╨╛╤З╨╜╨╛"],
                ["today", "╨б╨╡╨│╨╛╨┤╨╜╤П"],
                ["reply", "╨Ь╨╛╨╣ ╨╛╤В╨▓╨╡╤В"],
                ["docs", "╨Ф╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л"],
                ["payment", "╨Ю╨┐╨╗╨░╤В╨░"],
                ["sla", "╨а╨╕╤Б╨║ SLA"],
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
                    <th>╨Я╤А╨╕╨╛╤А╨╕╤В╨╡╤В</th>
                    <th>╨Ф╨╡╨╗╨╛</th>
                    <th>╨н╤В╨░╨┐</th>
                    <th>╨Я╨╛╤Б╨╗╨╡╨┤╨╜╨╡╨╡ ╤Б╨╛╨▒╤Л╤В╨╕╨╡</th>
                    <th>╨б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╣ ╤И╨░╨│</th>
                    <th>╨Ф╨╡╨┤╨╗╨░╨╣╨╜</th>
                    <th>╨Ъ╨░╨╜╨░╨╗</th>
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
                        <td>{item.client_name ?? "╨Ъ╨╗╨╕╨╡╨╜╤В"}</td>
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
                            ╨Ю╤В╨║╤А╤Л╤В╤М
                  </button>
                        </td>
                      </tr>
              ))}
                </tbody>
              </table>
            </div>
          </div>

              <div className="panel">
            <h2>╨Ф╨╡╨╗╨░ ╨┐╨╛ ╤Н╤В╨░╨┐╨░╨╝</h2>
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
            { value: "DIAG", label: "╨Ф╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░" },
            { value: "ACCOMP", label: "╨б╨╛╨┐╤А╨╛╨▓╨╛╨╢╨┤╨╡╨╜╨╕╨╡" },
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
            staffToken={token}
            apiBase={apiBase}
            onDeliveryNotice={setNotice}
            onDeliveryRefresh={() => void openCase(detail.id)}
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

          {token ? (
            <IngestReviewPanel
              caseId={detail.id}
              token={token}
              busy={busy}
              canEdit={detail.role_capabilities.can_view_ocr}
              onNotice={setNotice}
              onRefresh={() => void openCase(detail.id)}
            />
          ) : null}

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
                <h3>╨б╨╛╨╖╨┤╨░╤В╤М ╨╖╨░╨┤╨░╤З╤Г ╨▓ Tracker</h3>
                <p className="hint" style={{ color: "#b91c1c" }}>
                  ╨Э╨╡ ╤Г╨║╨░╨╖╤Л╨▓╨░╨╣╤В╨╡ ╨д╨Ш╨Ю, ╤В╨╡╨╗╨╡╤Д╨╛╨╜, e-mail, ╨б╨Э╨Ш╨Ы╨б, ╨╜╨╛╨╝╨╡╤А╨░ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓, ╤Б╤Б╤Л╨╗╨║╨╕ ╨╜╨░ ╨║╨░╨▒╨╕╨╜╨╡╤В,
                  ╤Д╨░╨╣╨╗╤Л, ╤В╨╡╨║╤Б╤В ╨┐╨╡╤А╨╡╨┐╨╕╤Б╨║╨╕ ╨╕╨╗╨╕ ╤Б╨╛╨┤╨╡╤А╨╢╨░╨╜╨╕╨╡ ╨Ш╨Ы╨б.
                </p>
                <div className="stack-form">
                  <label>
                    ╨в╨╕╨┐
                    <select
                      value={trackerIssueType}
                      onChange={(e) => setTrackerIssueType(e.target.value)}
                    >
                      <option value="bug">╨Ю╤И╨╕╨▒╨║╨░</option>
                      <option value="sla_incident">╨Ш╨╜╤Ж╨╕╨┤╨╡╨╜╤В SLA</option>
                      <option value="channel_conflict">╨Ъ╨╛╨╜╤Д╨╗╨╕╨║╤В ╨║╨░╨╜╨░╨╗╨╛╨▓</option>
                      <option value="process_improvement">╨г╨╗╤Г╤З╤И╨╡╨╜╨╕╨╡ ╨┐╤А╨╛╤Ж╨╡╤Б╤Б╨░</option>
                      <option value="development">╨а╨░╨╖╤А╨░╨▒╨╛╤В╨║╨░</option>
                      <option value="content">╨Ъ╨╛╨╜╤В╨╡╨╜╤В</option>
                      <option value="security_privacy">╨С╨╡╨╖╨╛╨┐╨░╤Б╨╜╨╛╤Б╤В╤М / ╨Я╨Ф╨╜</option>
                      <option value="analytics_hypothesis">╨Р╨╜╨░╨╗╨╕╤В╨╕╤З╨╡╤Б╨║╨░╤П ╨│╨╕╨┐╨╛╤В╨╡╨╖╨░</option>
                      <option value="partner_request">╨Я╨░╤А╤В╨╜╤С╤А╤Б╨║╨╕╨╣ ╨╖╨░╨┐╤А╨╛╤Б</option>
                    </select>
                  </label>
                  <label>
                    ╨Я╤А╨╕╨╛╤А╨╕╤В╨╡╤В
                    <select
                      value={trackerPriority}
                      onChange={(e) => setTrackerPriority(e.target.value)}
                    >
                      <option value="critical">╨Ъ╤А╨╕╤В╨╕╤З╨╡╤Б╨║╨╕╨╣</option>
                      <option value="high">╨Т╤Л╤Б╨╛╨║╨╕╨╣</option>
                      <option value="normal">╨Ю╨▒╤Л╤З╨╜╤Л╨╣</option>
                      <option value="low">╨Э╨╕╨╖╨║╨╕╨╣</option>
                    </select>
                  </label>
                  <label>
                    ╨Э╨░╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╨╡
                    <select
                      value={trackerDirection}
                      onChange={(e) => setTrackerDirection(e.target.value)}
                    >
                      <option value="ops">╨Ю╨┐╨╡╤А╨░╤Ж╨╕╨╕</option>
                      <option value="product">╨Я╤А╨╛╨┤╤Г╨║╤В</option>
                      <option value="dev">╨а╨░╨╖╤А╨░╨▒╨╛╤В╨║╨░</option>
                      <option value="content">╨Ъ╨╛╨╜╤В╨╡╨╜╤В</option>
                      <option value="security">╨С╨╡╨╖╨╛╨┐╨░╤Б╨╜╨╛╤Б╤В╤М</option>
                      <option value="partners">╨Я╨░╤А╤В╨╜╤С╤А╤Л</option>
                    </select>
                  </label>
                  <label>
                    ╨Я╨╛╨▓╤В╨╛╤А╤П╨╡╨╝╨╛╤Б╤В╤М
                    <select value={trackerRepeat} onChange={(e) => setTrackerRepeat(e.target.value)}>
                      <option value="once">╨Х╨┤╨╕╨╜╨╕╤З╨╜╨╛</option>
                      <option value="recurring">╨Я╨╛╨▓╤В╨╛╤А╤П╨╡╤В╤Б╤П</option>
                      <option value="systemic">╨б╨╕╤Б╤В╨╡╨╝╨╜╨╛</option>
                    </select>
                  </label>
                  <label>
                    ╨Ъ╤А╨░╤В╨║╨╕╨╣ ╨╖╨░╨│╨╛╨╗╨╛╨▓╨╛╨║ (╨╛╨┐╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╨╛)
                    <input
                      value={trackerTitle}
                      onChange={(e) => setTrackerTitle(e.target.value)}
                      placeholder="╨С╨╡╨╖ ╨Я╨Ф╨╜"
                      maxLength={120}
                    />
                  </label>
                  <label>
                    ╨Ю╨▒╨╡╨╖╨╗╨╕╤З╨╡╨╜╨╜╨╛╨╡ ╨╛╨┐╨╕╤Б╨░╨╜╨╕╨╡
                    <textarea
                      rows={5}
                      value={trackerDesc}
                      onChange={(e) => setTrackerDesc(e.target.value)}
                      placeholder="╨з╤В╨╛ ╨╜╨╡ ╤В╨░╨║ / ╤З╤В╨╛ ╤Г╨╗╤Г╤З╤И╨╕╤В╤М тАФ ╨▒╨╡╨╖ ╨┐╨╡╤А╤Б╨╛╨╜╨░╨╗╤М╨╜╤Л╤Е ╨┤╨░╨╜╨╜╤Л╤Е"
                      required
                    />
                  </label>
                  <label className="inline-form">
                    <input
                      type="checkbox"
                      checked={trackerForceNew}
                      onChange={(e) => setTrackerForceNew(e.target.checked)}
                    />
                    ╨б╨╛╨╖╨┤╨░╤В╤М ╨╜╨╛╨▓╤Г╤О, ╨┤╨░╨╢╨╡ ╨╡╤Б╨╗╨╕ ╨╡╤Б╤В╤М ╨╛╤В╨║╤А╤Л╤В╨░╤П ╤В╨╛╨│╨╛ ╨╢╨╡ ╤В╨╕╨┐╨░
                  </label>
                  <p className="hint">
                    ╨Т Tracker ╤Г╨╣╨┤╤С╤В ╨┐╤Б╨╡╨▓╨┤╨╛╨╜╨╕╨╝ ╨┤╨╡╨╗╨░ (case_ref), ╤Н╤В╨░╨┐ {detail.pipeline_status}, ╤В╨╕╨┐ ╨╕
                    ╨╛╨┐╨╕╤Б╨░╨╜╨╕╨╡. ╨Ю╤З╨╡╤А╨╡╨┤╤М STAZH.
                  </p>
                </div>
                <div className="dup-dialog-actions">
                  <button type="button" className="ghost" onClick={() => setTrackerModalOpen(false)}>
                    ╨Ю╤В╨╝╨╡╨╜╨░
                  </button>
                  <button type="button" disabled={busy} onClick={() => void createTrackerIssue()}>
                    ╨б╨╛╨╖╨┤╨░╤В╤М ╨▓ Tracker
                  </button>
                </div>
              </div>
            </div>
          ) : null}
          {dupDialog ? (
            <div className="dup-dialog-backdrop" role="dialog" aria-modal="true">
              <div className="dup-dialog">
                <h3>╨Я╨╛╨▓╤В╨╛╤А ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П</h3>
                <p>
                  ╨н╤В╨╛╤В ╨╖╨░╨┐╤А╨╛╤Б ╤Г╨╢╨╡ ╨╛╤В╨┐╤А╨░╨▓╨╗╤П╨╗╤Б╤П
                  {dupDialog.lastAt
                    ? ` ${new Date(dupDialog.lastAt).toLocaleString("ru-RU", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}`
                    : " ╤Б╨╡╨│╨╛╨┤╨╜╤П"}
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
                    ╨Ю╤В╨║╤А╤Л╤В╤М ╨┐╨╛╤Б╨╗╨╡╨┤╨╜╨╡╨╡
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
                          "╨Я╨╛╤Е╨╛╨╢╨╕╤Е ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣ ╤Г╨╢╨╡ ╨╜╨╡╤Б╨║╨╛╨╗╤М╨║╨╛ ╨╖╨░ 48 ╤З╨░╤Б╨╛╨▓. ╨Ю╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨┐╨╛╨▓╤В╨╛╤А╨╜╨╛?",
                        )
                      ) {
                        return;
                      }
                      void sendMaxReply({ force: true });
                    }}
                  >
                    ╨Ю╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨┐╨╛╨▓╤В╨╛╤А╨╜╨╛
                  </button>
                  <button type="button" className="ghost" onClick={() => setDupDialog(null)}>
                    ╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М
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
              <h2>╨б╨╛╨╖╨┤╨░╤В╤М ╤Б╤З╤С╤В</h2>
              <form className="stack-form" onSubmit={(e) => void createFinanceInvoice(e)}>
                <label>
                  ╨Ф╨╡╨╗╨╛
                  <select value={invoiceCaseId} onChange={(e) => setInvoiceCaseId(e.target.value)} required>
                    <option value="">╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╨┤╨╡╨╗╨╛</option>
                    {cases.filter((c) => !c.is_test).map((c) => (
                      <option key={c.id} value={c.id}>{c.client_name ?? "╨Ъ╨╗╨╕╨╡╨╜╤В"} ┬╖ {c.id.slice(0, 8)}</option>
                    ))}
                </select>
                </label>
                <label>
                  ╨г╤Б╨╗╤Г╨│╨░ ╤Б /tarify/
                  <select
                    value={`${invoiceCode}:${invoiceAmount}:${invoiceLabel}`}
                    onChange={(e) => {
                      const [code, amount, ...rest] = e.target.value.split(":");
                      setInvoiceCode((code as "DIAG" | "ACCOMP") || "DIAG");
                      setInvoiceAmount(amount || "3000");
                      setInvoiceLabel(rest.join(":") || "╨Ф╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░");
                    }}
                  >
                    <option value="DIAG:3000:╨Ф╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░">╨Ф╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░ ┬╖ 3 000 тВ╜</option>
                    <option value="ACCOMP:5000:╨Я╨╛╨┤╨│╨╛╤В╨╛╨▓╨║╨░ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓">╨Я╨╛╨┤╨│╨╛╤В╨╛╨▓╨║╨░ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓ ┬╖ 5 000 тВ╜</option>
                    <option value="ACCOMP:8000:╨б╨╛╨┐╤А╨╛╨▓╨╛╨╢╨┤╨╡╨╜╨╕╨╡ ╨┤╨╛ ╨┐╨╛╨┤╨░╤З╨╕">╨б╨╛╨┐╤А╨╛╨▓╨╛╨╢╨┤╨╡╨╜╨╕╨╡ ╨┤╨╛ ╨┐╨╛╨┤╨░╤З╨╕ ┬╖ 8 000 тВ╜</option>
                  </select>
                </label>
                <label>╨б╤Г╨╝╨╝╨░ тВ╜<input type="number" min={1} step="0.01" value={invoiceAmount} onChange={(e) => setInvoiceAmount(e.target.value)} required /></label>
                <label>╨б╤А╨╛╨║ ╨╛╨┐╨╗╨░╤В╤Л<input type="datetime-local" value={invoiceDue} onChange={(e) => setInvoiceDue(e.target.value)} /></label>
                <p className="hint">╨Ю╨┐╨╗╨░╤В╨░ ╨╖╨░ ╨╕╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╨╛╨╜╨╜╨╛-╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨░╤А╨╜╤Г╤О ╨┐╨╛╨┤╨┤╨╡╤А╨╢╨║╤Г ╤Б╨╛╨│╨╗╨░╤Б╨╜╨╛ ╨▓╤Л╨▒╤А╨░╨╜╨╜╨╛╨╣ ╤Г╤Б╨╗╤Г╨│╨╡/╨┤╨╛╨│╨╛╨▓╨╛╤А╤Г.</p>
                <div className="inline-form">
                  <button type="submit">╨б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╤З╨╡╤А╨╜╨╛╨▓╨╕╨║</button>
                  <button type="button" className="ghost" onClick={() => setCreateInvoiceOpen(false)}>╨Ю╤В╨╝╨╡╨╜╨░</button>
            </div>
              </form>
            </section>
          )}

          {markPaidOrder && (
            <section className="panel stack finance-modal">
              <h2>╨Ю╤В╨╝╨╡╤В╨╕╤В╤М ╨╛╨┐╨╗╨░╤В╤Г ╨▓╤А╤Г╤З╨╜╤Г╤О</h2>
              <form className="stack-form" onSubmit={(e) => void submitMarkPaid(e)}>
                <label>╨Ф╨░╤В╨░ ╨╕ ╨▓╤А╨╡╨╝╤П<input type="datetime-local" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} required /></label>
                <label>╨б╤Г╨╝╨╝╨░ тВ╜<input type="number" min={1} step="0.01" value={paidAmount} onChange={(e) => setPaidAmount(e.target.value)} required /></label>
                <label>
                  ╨б╨┐╨╛╤Б╨╛╨▒
                  <select value={paidMethod} onChange={(e) => setPaidMethod(e.target.value)}>
                    <option value="transfer">╨Я╨╡╤А╨╡╨▓╨╛╨┤</option>
                    <option value="card">╨Ъ╨░╤А╤В╨░</option>
                    <option value="yookassa">╨оKassa</option>
                    <option value="cash">╨Э╨░╨╗╨╕╤З╨╜╤Л╨╡</option>
                    <option value="other">╨Ф╤А╤Г╨│╨╛╨╡</option>
                </select>
                </label>
                <label>╨Э╨╛╨╝╨╡╤А ╨╛╨┐╨╡╤А╨░╤Ж╨╕╨╕ / ╨║╨╛╨╝╨╝╨╡╨╜╤В╨░╤А╨╕╨╣<input value={paidRef} onChange={(e) => setPaidRef(e.target.value)} required /></label>
                <p className="hint">╨б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║ ╨╕ ╨▓╤А╨╡╨╝╤П ╨┐╨╛╨┐╨░╨┤╤Г╤В ╨▓ ╨╢╤Г╤А╨╜╨░╨╗ ╨░╤Г╨┤╨╕╤В╨░. ╨г╨┤╨░╨╗╨╕╤В╤М ╨╖╨░╨┐╨╕╤Б╤М ╤З╨╡╤А╨╡╨╖ ╨╕╨╜╤В╨╡╤А╤Д╨╡╨╣╤Б ╨╜╨╡╨╗╤М╨╖╤П.</p>
                <div className="inline-form">
                  <button type="submit">╨Ч╨░╨┐╨╕╤Б╨░╤В╤М ╨╛╨┐╨╗╨░╤В╤Г</button>
                  <button type="button" className="ghost" onClick={() => setMarkPaidOrder(null)}>╨Ю╤В╨╝╨╡╨╜╨░</button>
            </div>
            </form>
        </section>
      )}

          {cancelOrder && (
            <section className="panel stack finance-modal">
              <h2>╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М ╤Б╤З╤С╤В</h2>
              <form className="stack-form" onSubmit={(e) => void submitCancel(e)}>
                <label>
                  ╨Я╤А╨╕╤З╨╕╨╜╨░
                  <select value={cancelReason} onChange={(e) => setCancelReason(e.target.value)}>
                    <option value="refusal">╨Ю╤В╨║╨░╨╖</option>
                    <option value="duplicate">╨Ф╤Г╨▒╨╗╤М</option>
                    <option value="amount_error">╨Ю╤И╨╕╨▒╨║╨░ ╤Б╤Г╨╝╨╝╤Л</option>
                    <option value="no_contact">╨Э╨╡╤В ╤Б╨▓╤П╨╖╨╕</option>
                    <option value="other">╨Ф╤А╤Г╨│╨╛╨╡</option>
                  </select>
                </label>
                <label>╨Ъ╨╛╨╝╨╝╨╡╨╜╤В╨░╤А╨╕╨╣<input value={cancelComment} onChange={(e) => setCancelComment(e.target.value)} /></label>
                <div className="inline-form">
                  <button type="submit">╨Ю╤В╨╝╨╡╨╜╨╕╤В╤М ╤Б╤З╤С╤В</button>
                  <button type="button" className="ghost" onClick={() => setCancelOrder(null)}>╨Ч╨░╨║╤А╤Л╤В╤М</button>
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

      {busy && <p className="hint">╨Ч╨░╨│╤А╤Г╨╖╨║╨░тАж</p>}
    </main>
  );
}
