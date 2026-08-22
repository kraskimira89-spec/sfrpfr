"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import {
  formatCaseStatuses,
  labelAuthorKind,
  labelChecklistOwner,
  labelChecklistStatus,
  labelFeedbackQuality,
  labelOrderStatus,
  labelPackage,
  labelPipeline,
  labelStaffRole,
} from "@/lib/ui-labels";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

type StaffRole = "operator" | "expert" | "admin";

type Me = {
  user_id: string;
  email: string | null;
  role: StaffRole | null;
  is_staff: boolean;
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
  documents: { id: string; storage_path: string; doc_type?: string | null }[];
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
    max_business_url?: string | null;
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
  role_capabilities: RoleCapabilities;
  audit: { id?: number; action: string; at: string; actor_id?: string }[];
  orders?: { id: string; package_code: string; amount_rub: number; status: string }[];
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

/** Экран входа: MAX (основной) | код на почту (запасной). Саморегистрации нет. */
type AuthScreen = "max" | "email_otp";

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

const CHANNEL_LABELS: Record<string, string> = {
  max_miniapp: "MAX",
  web_cabinet: "Веб-кабинет",
  unset: "не выбран",
};

/** Короткий номер дела (совпадает с кабинетом / MAX «Дело №»). */
function caseShortNumber(caseId: string): string {
  const hex = String(caseId || "").replace(/-/g, "").slice(-5);
  const n = Number.parseInt(hex, 16);
  if (!Number.isFinite(n) || n <= 0) return "—";
  return String(n).padStart(6, "0");
}

function caseCatalogLabel(caseId: string): string {
  return `ПС-${caseShortNumber(caseId)}`;
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
    throw new Error((await response.text()) || `HTTP ${response.status}`);
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
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [authScreen, setAuthScreen] = useState<AuthScreen>("max");
  const [maxTicket, setMaxTicket] = useState("");
  const [maxPairCode, setMaxPairCode] = useState("");
  const [maxWaitStatus, setMaxWaitStatus] = useState("");
  const [maxBotUrl, setMaxBotUrl] = useState(DEFAULT_MAX_OPS_BOT);
  const [maxReplyBody, setMaxReplyBody] = useState("");
  const [maxReplyFocus, setMaxReplyFocus] = useState(false);
  const [notice, setNotice] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<StaffCaseSummary[]>([]);
  const [detail, setDetail] = useState<StaffCaseDetail | null>(null);
  const [messages, setMessages] = useState<{ id: string; author_kind: string; body: string; created_at: string }[]>([]);
  const [messageBody, setMessageBody] = useState("");
  const [finance, setFinance] = useState<{ orders: StaffCaseDetail["orders"]; formula: string } | null>(null);
  const [analytics, setAnalytics] = useState<{
    rows: Record<string, unknown>[];
    aggregates: Record<string, unknown>;
    note: string;
  } | null>(null);
  const [roles, setRoles] = useState<{ user_id: string; role: string }[]>([]);
  const [busy, setBusy] = useState(false);

  const [q, setQ] = useState("");
  const [filterPipeline, setFilterPipeline] = useState("");
  const [filterChannel, setFilterChannel] = useState("");
  const [filterPackage, setFilterPackage] = useState("");

  const [checklistTitle, setChecklistTitle] = useState("");
  const [pipelineStatus, setPipelineStatus] = useState("human_review");
  const [beforeRub, setBeforeRub] = useState("");
  const [afterRub, setAfterRub] = useState("");
  const [lumpRub, setLumpRub] = useState("0");
  const [feedbackQuality, setFeedbackQuality] = useState("verified");
  const [feedbackText, setFeedbackText] = useState("");
  const [newRoleUserId, setNewRoleUserId] = useState("");
  const [newRole, setNewRole] = useState<StaffRole>("operator");
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

  const loadCases = useCallback(async () => {
    if (!token) return;
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (filterPipeline) params.set("pipeline_status", filterPipeline);
    if (filterChannel) params.set("preferred_channel", filterChannel);
    if (filterPackage) params.set("package_code", filterPackage);
    const qs = params.toString();
    setCases(
      await apiFetch<StaffCaseSummary[]>(
        `/api/portal/admin/cases${qs ? `?${qs}` : ""}`,
        token,
      ),
    );
  }, [token, q, filterPipeline, filterChannel, filterPackage]);

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
    setNotice("");
    if (next === "max") resetMaxWizard();
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

  async function openCase(caseId: string, opts?: { focusMaxReply?: boolean }) {
    if (!token) return;
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
      setView("case");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setNotice(
        detail.includes("case not found") || detail.includes("404")
          ? "Дело не найдено или недоступно для вашей роли."
          : `Не удалось открыть дело: ${detail || "ошибка API"}`,
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!token || !me?.is_staff) return;
    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("case")?.trim();
    const focusMax = window.location.hash === "#max-reply";
    if (caseId) {
      void (async () => {
        if (!token) return;
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
            // см. openCase
          }
          setDetail(caseDetail);
          setMessages(caseMessages);
          setPipelineStatus(caseDetail.pipeline_status);
          setView("case");
          if (focusMax) setMaxReplyFocus(true);
        } catch (err) {
          const detail = err instanceof Error ? err.message : "";
          setNotice(
            detail.includes("case not found") || detail.includes("404")
              ? "Дело не найдено или недоступно для вашей роли."
              : `Не удалось открыть дело: ${detail || "ошибка API"}`,
          );
        } finally {
          setBusy(false);
        }
      })();
    }
  }, [token, me?.is_staff]);

  useEffect(() => {
    if (view !== "case" || !detail || !maxReplyFocus) return;
    window.requestAnimationFrame(() => {
      document.getElementById("max-reply-panel")?.scrollIntoView({ behavior: "smooth" });
      document.getElementById("max-reply-text")?.focus();
      setMaxReplyFocus(false);
    });
  }, [view, detail, maxReplyFocus]);

  async function loadFinance() {
    if (!token) return;
    setBusy(true);
    try {
      setFinance(await apiFetch("/api/portal/admin/finance", token));
      setView("finance");
    } catch {
      setNotice("Финансы недоступны для роли оператора.");
    } finally {
      setBusy(false);
    }
  }

  async function loadAnalytics() {
    if (!token) return;
    setBusy(true);
    try {
      setAnalytics(await apiFetch("/api/portal/admin/analytics", token));
      setView("analytics");
    } catch {
      setNotice("Аналитика недоступна для роли оператора.");
    } finally {
      setBusy(false);
    }
  }

  async function loadRoles() {
    if (!token) return;
    setBusy(true);
    try {
      setRoles(await apiFetch("/api/portal/admin/staff-roles", token));
      setView("roles");
    } catch {
      setNotice("Управление ролями только у администратора.");
    } finally {
      setBusy(false);
    }
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

  async function sendMaxReply(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail || !maxReplyBody.trim() || !detail.client.max_linked) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/cases/${detail.id}/max-reply`, token, {
        method: "POST",
        body: JSON.stringify({ message: maxReplyBody.trim() }),
      });
      setMaxReplyBody("");
      setNotice("Сообщение отправлено клиенту в MAX.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось отправить в MAX.");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!token || !detail || !messageBody.trim()) return;
    await apiFetch(`/api/portal/cases/${detail.id}/messages`, token, {
      method: "POST",
      body: JSON.stringify({ body: messageBody.trim() }),
    });
    setMessageBody("");
    const next = await apiFetch<typeof messages>(`/api/portal/cases/${detail.id}/messages`, token);
    setMessages(next);
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

  async function saveRole(event: FormEvent) {
    event.preventDefault();
    if (!token || !newRoleUserId.trim()) return;
    await apiFetch(`/api/portal/admin/staff-roles/${newRoleUserId.trim()}`, token, {
      method: "PUT",
      body: JSON.stringify({ role: newRole }),
    });
    await loadRoles();
    setNotice("Роль сохранена.");
  }

  if (!session) {
    return (
      <main className="auth-layout">
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
              Проверка стажа · сотрудники
            </BrandHomeLink>
          </p>
          <h1>Кабинет сотрудника</h1>
          <p className="lead lead-compact">
            Вход через ops-бот MAX «Проверка стажа-Ops»: получите код на этой странице, подтвердите в MAX.
            Роль выдаёт администратор заранее — открытой регистрации нет.
          </p>

          {authScreen === "max" ? (
            <>
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
                <details>
                  <summary>Другие способы</summary>
                  <div className="auth-alt-list">
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => goAuthScreen("email_otp")}
                    >
                      Код на рабочую почту
                    </button>
                  </div>
                </details>
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

          {notice && <p className="notice">{notice}</p>}
          <p className="hint auth-staff-hint">
            Нет доступа? Попросите администратора добавить вас в разделе «Роли».
          </p>
        </section>
      </main>
    );
  }

  if (me && !me.is_staff) {
    return (
      <main className="auth-layout">
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
      </main>
    );
  }

  const caps = detail?.role_capabilities;

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
        {me?.role !== "operator" && (
          <button type="button" className={view === "analytics" ? "tab active" : "tab"} onClick={() => void loadAnalytics()}>
            Аналитика
          </button>
        )}
        {me?.role === "admin" && (
          <button type="button" className={view === "roles" ? "tab active" : "tab"} onClick={() => void loadRoles()}>
            Роли
          </button>
        )}
      </nav>

      {view === "dashboard" && dashboard && (
        <section className="stack">
          <h1>Дашборд</h1>
          <div className="metrics">
            <article><span>Новые заявки</span><strong>{dashboard.new_leads}</strong></article>
            <article><span>Оплаты: ожидают / оплачено</span><strong>{dashboard.payments_pending} / {dashboard.payments_paid}</strong></article>
            <article><span>Без ответа ≥30/90/150/180</span><strong>{dashboard.silent["30"]}/{dashboard.silent["90"]}/{dashboard.silent["150"]}/{dashboard.silent["180"]}</strong></article>
            <article><span>Конфликты каналов (ТЗ-09)</span><strong>{dashboard.channel_conflicts}</strong></article>
            <article><span>Без MAX / без веб-кабинета</span><strong>{dashboard.unlinked_max} / {dashboard.unlinked_web}</strong></article>
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
        <section className="stack">
          <h1>Реестр дел</h1>
          <form
            className="filters"
            onSubmit={(e) => {
              e.preventDefault();
              void loadCases();
            }}
          >
            <input
              placeholder="Поиск: case_id, имя, телефон"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <select value={filterPipeline} onChange={(e) => setFilterPipeline(e.target.value)}>
              <option value="">Все этапы</option>
              {["intake", "documents_received", "audited", "draft_ready", "human_review", "completed"].map((s) => (
                <option key={s} value={s}>{labelPipeline(s)}</option>
              ))}
            </select>
            <select value={filterChannel} onChange={(e) => setFilterChannel(e.target.value)}>
              <option value="">Все каналы</option>
              <option value="max_miniapp">MAX</option>
              <option value="web_cabinet">Веб</option>
              <option value="unset">Не выбран</option>
            </select>
            <select value={filterPackage} onChange={(e) => setFilterPackage(e.target.value)}>
              <option value="">Все услуги</option>
              <option value="DIAG">Диагностика</option>
              <option value="ACCOMP">Сопровождение</option>
              <option value="SF_LUMP">{labelPackage("SF_LUMP")}</option>
              <option value="SF_MONTH">{labelPackage("SF_MONTH")}</option>
            </select>
            <button type="submit">Применить</button>
          </form>
          <ul className="case-list">
            {cases.map((item) => (
              <li key={item.id}>
                <button type="button" className="case-card-button" onClick={() => void openCase(item.id)}>
                  <strong>
                    {item.client_name ?? "Клиент"} · {caseCatalogLabel(item.id)}
                  </strong>
                  <span>
                    {formatCaseStatuses(item.pipeline_status, item.b2c_status)}
                  </span>
                  <span>
                    Канал: {CHANNEL_LABELS[item.preferred_channel] ?? item.preferred_channel}
                    {" · "}MAX {item.max_linked ? "✓" : "—"} · веб {item.web_linked ? "✓" : "—"}
                  </span>
                  <span>
                    Тишина: {item.silent_days} дн. · чек-лист открыт: {item.checklist_open_count}
                    {item.client_phone ? ` · ${item.client_phone}` : ""}
                  </span>
                  {item.crm_url && (
                    <span>
                      amoCRM: <a href={item.crm_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>открыть</a>
                    </span>
                  )}
                  {item.max_linked && (
                    <span>
                      <button
                        type="button"
                        className="linkish"
                        onClick={(e) => {
                          e.stopPropagation();
                          void openCase(item.id, { focusMaxReply: true });
                        }}
                      >
                        Написать в MAX
                      </button>
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {view === "case" && detail && (
        <section className="stack">
          <button type="button" className="ghost" onClick={() => setView("cases")}>← К реестру</button>
          <h1>
            {detail.client.full_name ?? "Клиент"} · {caseCatalogLabel(detail.id)}
          </h1>
          <p className="warning inline">{detail.warning}</p>
          <p>
            {formatCaseStatuses(detail.pipeline_status, detail.b2c_status)}
            {detail.client.phone ? ` · ${detail.client.phone}` : ""}
            {detail.client.email ? ` · ${detail.client.email}` : ""}
          </p>

          <div className="panel accent">
            <h2>Каналы клиента (ТЗ-09)</h2>
            <p>
              Предпочтение: <strong>{CHANNEL_LABELS[detail.client.preferred_channel] ?? detail.client.preferred_channel}</strong>
            </p>
            <p>
              MAX: {detail.client.max_linked ? "привязан" : "нет"}
              {detail.client.max_user_id ? ` · user_id ${detail.client.max_user_id}` : ""}
              {" · "}веб-кабинет: {detail.client.web_linked ? "привязан" : "нет"}
            </p>
            <p className="hint">
              Веб-кабинет клиента и мини-приложение MAX — одно дело. Ответ клиенту в MAX — из этого кабинета
              или MAX Business, не через ссылку на клиентского бота.
            </p>
            <div className="row-actions">
              <a href={detail.channels.cabinet_url} target="_blank" rel="noreferrer">Веб-кабинет клиента</a>
              {detail.client.max_linked ? (
                <button
                  type="button"
                  className="max-action-btn max-action-btn--inline"
                  disabled={busy}
                  onClick={focusMaxReplyPanel}
                >
                  Написать в MAX
                </button>
              ) : null}
              {detail.channels.max_business_url && (
                <a href={detail.channels.max_business_url} target="_blank" rel="noreferrer">
                  MAX Business → диалоги
                </a>
              )}
              {detail.crm_url && (
                <a href={detail.crm_url} target="_blank" rel="noreferrer">amoCRM</a>
              )}
              {detail.meeting_url && (
                <a href={detail.meeting_url} target="_blank" rel="noreferrer">Телемост</a>
              )}
            </div>

            <div className="panel" id="max-reply-panel">
              <h3>Написать клиенту в MAX</h3>
              {!detail.client.max_linked ? (
                <p className="hint">У клиента нет MAX user_id — ответ через MAX недоступен.</p>
              ) : (
                <form className="stack-form" onSubmit={(e) => void sendMaxReply(e)}>
                  <textarea
                    id="max-reply-text"
                    rows={3}
                    value={maxReplyBody}
                    onChange={(e) => setMaxReplyBody(e.target.value)}
                    placeholder="Текст сообщения клиенту (бот «Проверка стажа-личный бот» в MAX)"
                    required
                    disabled={busy}
                  />
                  <button type="submit" className="max-action-btn max-action-btn--inline" disabled={busy}>
                    Отправить в MAX
                  </button>
                </form>
              )}
              <p className="hint">
                Ссылка max.ru/…_1_bot открывает ваш личный чат с ботом, не переписку клиента. Здесь сообщение
                уходит клиенту через API.
                {detail.channels.max_business_url && detail.client.max_user_id
                  ? ` В MAX Business → «Проверка стажа-личный бот» → Диалоги → user_id ${detail.client.max_user_id}.`
                  : ""}
              </p>
            </div>

            <div className="row-actions">
              <button type="button" onClick={() => void requestReview()} disabled={busy}>
                Запустить проверку
              </button>
              <button type="button" onClick={() => void createTelemost()} disabled={busy}>
                Создать Телемост
              </button>
              <button type="button" onClick={() => void sendWorkspaceEmail()} disabled={busy}>
                Письмо: запрос документов
              </button>
            </div>
          </div>

          <div className="panel">
            <h2>Законные представители</h2>
            <p className="hint">
              Доступ только к этому делу. У представителя должен быть вход в веб-кабинет (email).
            </p>
            <ul className="plain-list">
              {(detail.representatives ?? []).length === 0 && <li>Пока нет</li>}
              {(detail.representatives ?? []).map((rep) => (
                <li key={rep.user_id}>
                  {rep.full_name || rep.email || rep.user_id.slice(0, 8)}
                  {" "}
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => void removeRepresentative(rep.user_id)}
                  >
                    Снять доступ
                  </button>
                </li>
              ))}
            </ul>
            <form className="row-actions" onSubmit={(e) => void addRepresentative(e)}>
              <input
                type="email"
                placeholder="email представителя"
                value={repEmail}
                onChange={(e) => setRepEmail(e.target.value)}
                required
              />
              <button type="submit" disabled={busy}>
                Выдать доступ
              </button>
            </form>
          </div>

          <div className="panel">
            <h2>Документы</h2>
            <ul className="plain-list">
              {detail.documents.length === 0 && <li>Документов нет</li>}
              {detail.documents.map((doc) => (
                <li key={doc.id}>
                  <button type="button" className="linkish" onClick={() => void openSigned(doc.id)}>
                    {doc.storage_path.split("/").pop()}
                  </button>
                  {doc.doc_type ? ` · ${doc.doc_type}` : ""}
                </li>
              ))}
            </ul>
          </div>

          {caps?.can_view_ocr && (
            <>
              <div className="panel">
                <h2>Распознавание / ИЛС / трудовая / замечания</h2>
                <p className="hint">Фрагментов распознанного текста: {(detail.ocr_texts ?? []).length}</p>
                <p className="hint">Периоды ИЛС: {(detail.ils_periods ?? []).length} · трудовая: {(detail.labor_periods ?? []).length}</p>
                <ul className="plain-list">
                  {(detail.findings ?? []).length === 0 && <li>Замечаний пока нет</li>}
                  {(detail.findings ?? []).map((f, idx) => (
                    <li key={`${f.type}-${idx}`}>
                      <strong>{f.type}</strong>
                      <span>{f.detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="panel">
                <h2>Обоснование аналитика (DeepSeek)</h2>
                <p className="hint">
                  После детерминированной сверки ИЛС↔трудовая. Не заменяет проверку эксперта.
                </p>
                {detail.analysis_notes ? (
                  <pre className="draft">{detail.analysis_notes}</pre>
                ) : (
                  <p>Обоснования пока нет — запустите проверку до этапа «Сверка завершена» или «Черновик готов».</p>
                )}
              </div>
              <div className="panel">
                <h2>Черновик заявления (YandexGPT)</h2>
                {detail.draft ? (
                  <pre className="draft">{detail.draft.title}{"\n\n"}{detail.draft.body}</pre>
                ) : (
                  <p>Черновика нет</p>
                )}
              </div>
            </>
          )}

          <div className="panel">
            <h2>Чек-лист</h2>
            <ul className="plain-list">
              {detail.checklist_items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="linkish"
                    disabled={!caps?.can_edit_checklist}
                    onClick={() => void toggleChecklist(item.id, item.status)}
                  >
                    [{labelChecklistStatus(item.status)}] {item.title}
                  </button>
                  <span className="hint"> · {labelChecklistOwner(item.owner)}</span>
                </li>
              ))}
            </ul>
            {caps?.can_edit_checklist && (
              <form className="inline-form" onSubmit={addChecklist}>
                <input
                  value={checklistTitle}
                  onChange={(e) => setChecklistTitle(e.target.value)}
                  placeholder="Новый пункт"
                  required
                />
                <button type="submit">Добавить</button>
              </form>
            )}
          </div>

          {caps?.can_edit_pipeline && (
            <div className="panel">
              <h2>Этап дела</h2>
              <div className="inline-form">
                <select value={pipelineStatus} onChange={(e) => setPipelineStatus(e.target.value)}>
                  {["intake", "documents_received", "ocr_done", "classified", "extracted", "audited", "draft_ready", "human_review", "completed", "failed"].map((s) => (
                    <option key={s} value={s}>{labelPipeline(s)}</option>
                  ))}
                </select>
                <button type="button" onClick={() => void savePipeline()}>Сохранить этап</button>
              </div>
            </div>
          )}

          {caps?.can_confirm_result && (
            <div className="panel">
              <h2>Подтверждение результата</h2>
              <form className="stack-form" onSubmit={confirmResult}>
                <label>Прежний размер ₽<input value={beforeRub} onChange={(e) => setBeforeRub(e.target.value)} required /></label>
                <label>Новый размер ₽<input value={afterRub} onChange={(e) => setAfterRub(e.target.value)} required /></label>
                <label>ЕДВ ₽<input value={lumpRub} onChange={(e) => setLumpRub(e.target.value)} /></label>
                <button type="submit">Подтвердить результат</button>
              </form>
              {detail.result?.success_fee && (
                <p className="hint">
                  Вознаграждение: {detail.result.success_fee.sf_total} ₽ (ЕДВ {detail.result.success_fee.sf_lump} + прибавка {detail.result.success_fee.sf_month})
                </p>
              )}
            </div>
          )}

          {caps?.can_manage_orders && (
            <div className="panel">
              <h2>Создать счёт</h2>
              <form className="inline-form" onSubmit={createOrder}>
                <select value={orderCode} onChange={(e) => setOrderCode(e.target.value as typeof orderCode)}>
                  <option value="DIAG">{labelPackage("DIAG")}</option>
                  <option value="ACCOMP">{labelPackage("ACCOMP")}</option>
                  <option value="SF_LUMP">{labelPackage("SF_LUMP")}</option>
                  <option value="SF_MONTH">{labelPackage("SF_MONTH")}</option>
                </select>
                <input
                  type="number"
                  min={1}
                  step="0.01"
                  placeholder="Сумма ₽"
                  value={orderAmount}
                  onChange={(e) => setOrderAmount(e.target.value)}
                  required
                />
                <button type="submit">Создать</button>
              </form>
              <p className="hint">Счета за результат (SF_*) — только после подтверждения и окна 60+ дней.</p>
            </div>
          )}

          {caps?.can_knowledge_feedback && (
            <div className="panel">
              <h2>Обратная связь для базы знаний</h2>
              <form className="stack-form" onSubmit={sendFeedback}>
                <textarea
                  rows={3}
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                  placeholder="Что сработало / документы / итог СФР"
                  required
                />
                <select value={feedbackQuality} onChange={(e) => setFeedbackQuality(e.target.value)}>
                  <option value="draft">{labelFeedbackQuality("draft")}</option>
                  <option value="verified">{labelFeedbackQuality("verified")}</option>
                  <option value="template">{labelFeedbackQuality("template")}</option>
                  <option value="rejected">{labelFeedbackQuality("rejected")}</option>
                </select>
                <button type="submit">Сохранить в базу знаний</button>
              </form>
            </div>
          )}

          <div className="panel">
            <h2>Сообщения</h2>
            <ul className="messages">
              {messages.map((m) => (
                <li key={m.id}>
                  <span className="meta">{labelAuthorKind(m.author_kind)} · {new Date(m.created_at).toLocaleString("ru-RU")}</span>
                  <p>{m.body}</p>
                </li>
              ))}
            </ul>
            <form className="stack-form" onSubmit={sendMessage}>
              <textarea rows={2} value={messageBody} onChange={(e) => setMessageBody(e.target.value)} required />
              <button type="submit">Отправить</button>
            </form>
          </div>

          <div className="panel">
            <h2>Журнал действий</h2>
            <ul className="plain-list">
              {detail.audit.slice(0, 40).map((row, idx) => (
                <li key={`${row.at}-${idx}`}>
                  {row.action} · {new Date(row.at).toLocaleString("ru-RU")}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {view === "finance" && finance && (
        <section className="stack">
          <h1>Финансы</h1>
          <p>{finance.formula}</p>
          <ul className="case-list">
            {(finance.orders ?? []).map((order) => (
              <li key={order.id}>
                <strong>{labelPackage(order.package_code)}</strong>
                <span>{order.amount_rub} ₽ · {labelOrderStatus(order.status)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {view === "analytics" && analytics && (
        <section className="stack">
          <h1>Аналитика (без ПДн)</h1>
          <p className="hint">{analytics.note}</p>
          <pre className="draft">{JSON.stringify(analytics.aggregates, null, 2)}</pre>
          <p>Обезличенных строк: {analytics.rows.length}</p>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard.writeText(JSON.stringify(analytics.rows, null, 2));
              setNotice("Обезличенные строки скопированы в буфер.");
            }}
          >
            Копировать обезличенный JSON
          </button>
        </section>
      )}

      {view === "roles" && (
        <section className="stack">
          <h1>Роли сотрудников</h1>
          <ul className="plain-list">
            {roles.map((row) => (
              <li key={row.user_id}>{row.user_id} · {labelStaffRole(row.role)}</li>
            ))}
          </ul>
          <form className="inline-form" onSubmit={saveRole}>
            <input
              placeholder="ID пользователя (uuid)"
              value={newRoleUserId}
              onChange={(e) => setNewRoleUserId(e.target.value)}
              required
            />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value as StaffRole)}>
              <option value="operator">{labelStaffRole("operator")}</option>
              <option value="expert">{labelStaffRole("expert")}</option>
              <option value="admin">{labelStaffRole("admin")}</option>
            </select>
            <button type="submit">Сохранить роль</button>
          </form>
        </section>
      )}

      {notice && <p className="notice">{notice}</p>}
      {busy && <p className="hint">Загрузка…</p>}
    </main>
  );
}
