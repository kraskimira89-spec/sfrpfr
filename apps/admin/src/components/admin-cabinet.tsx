"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

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
  ocr_texts?: unknown[];
  ils_periods?: unknown[];
  labor_periods?: unknown[];
  draft?: { title?: string; body?: string } | null;
  channels: { cabinet_url: string; max_bot_url: string; max_miniapp_url: string };
  crm_url?: string | null;
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

const CHANNEL_LABELS: Record<string, string> = {
  max_miniapp: "MAX",
  web_cabinet: "Веб-кабинет",
  unset: "не выбран",
};

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
      setNotice("Не удалось отправить код.");
      return;
    }
    setOtpSent(true);
    setNotice("Код отправлен на рабочий email.");
  }

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

  async function openCase(caseId: string) {
    if (!token) return;
    setBusy(true);
    try {
      const [caseDetail, caseMessages] = await Promise.all([
        apiFetch<StaffCaseDetail>(`/api/portal/admin/cases/${caseId}`, token),
        apiFetch<{ id: string; author_kind: string; body: string; created_at: string }[]>(
          `/api/portal/cases/${caseId}/messages`,
          token,
        ),
      ]);
      setDetail(caseDetail);
      setMessages(caseMessages);
      setPipelineStatus(caseDetail.pipeline_status);
      setView("case");
    } catch {
      setNotice("Дело недоступно для вашей роли.");
    } finally {
      setBusy(false);
    }
  }

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
    setNotice(`Обратная связь для RAG сохранена (${feedbackQuality}).`);
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
        <section className="card">
          <p className="eyebrow">SFRFR / INTERNAL</p>
          <h1>Кабинет сотрудника</h1>
          <p className="lead">Вход по одноразовому коду. Роль проверяется на сервере.</p>
          {!otpSent ? (
            <form onSubmit={signIn}>
              <label htmlFor="email">Рабочий email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <button type="submit">Получить код</button>
            </form>
          ) : (
            <form onSubmit={verifyOtp}>
              <label htmlFor="otp">Код</label>
              <input id="otp" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} required />
              <button type="submit">Войти</button>
            </form>
          )}
          {notice && <p className="notice">{notice}</p>}
        </section>
      </main>
    );
  }

  if (me && !me.is_staff) {
    return (
      <main className="auth-layout">
        <section className="card">
          <h1>Нет доступа</h1>
          <p>Учётка без staff-роли. Обратитесь к администратору.</p>
          <button type="button" onClick={() => void supabase?.auth.signOut()}>
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
        <div>
          <strong>SFRFR</strong>
          <span>
            Кабинет сотрудника · {me?.role ?? "…"} · {me?.email ?? ""}
          </span>
        </div>
        <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
          Выйти
        </button>
      </header>

      <section className="warning" role="note">
        Решение принимает СФР. Результат не гарантирован. Admin-функции не переносятся в MAX mini-app (ТЗ-09).
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
            <article><span>Оплаты pending / paid</span><strong>{dashboard.payments_pending} / {dashboard.payments_paid}</strong></article>
            <article><span>Без ответа ≥30/90/150/180</span><strong>{dashboard.silent["30"]}/{dashboard.silent["90"]}/{dashboard.silent["150"]}/{dashboard.silent["180"]}</strong></article>
            <article><span>Конфликты каналов (ТЗ-09)</span><strong>{dashboard.channel_conflicts}</strong></article>
            <article><span>Без MAX / без веб</span><strong>{dashboard.unlinked_max} / {dashboard.unlinked_web}</strong></article>
          </div>
          <div className="panel">
            <h2>Дела по этапам pipeline</h2>
            <ul className="plain-list">
              {Object.entries(dashboard.by_pipeline).map(([k, v]) => (
                <li key={k}>{k}: {v}</li>
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
                <option key={s} value={s}>{s}</option>
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
              <option value="SF_LUMP">SF lump</option>
              <option value="SF_MONTH">SF month</option>
            </select>
            <button type="submit">Применить</button>
          </form>
          <ul className="case-list">
            {cases.map((item) => (
              <li key={item.id}>
                <button type="button" className="case-card-button" onClick={() => void openCase(item.id)}>
                  <strong>{item.client_name ?? `Дело ${item.id.slice(0, 8)}`}</strong>
                  <span>{item.id} · {item.pipeline_status} · {item.b2c_status}</span>
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
                      Taganay: <a href={item.crm_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>открыть</a>
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
          <h1>{detail.client.full_name ?? `Дело ${detail.id.slice(0, 8)}`}</h1>
          <p className="warning inline">{detail.warning}</p>
          <p>
            {detail.pipeline_status} · {detail.b2c_status}
            {detail.client.phone ? ` · ${detail.client.phone}` : ""}
            {detail.client.email ? ` · ${detail.client.email}` : ""}
          </p>

          <div className="panel accent">
            <h2>Каналы клиента (ТЗ-09)</h2>
            <p>
              Предпочтение: <strong>{CHANNEL_LABELS[detail.client.preferred_channel] ?? detail.client.preferred_channel}</strong>
            </p>
            <p>
              MAX: {detail.client.max_linked ? "привязан" : "нет"} · веб-кабинет:{" "}
              {detail.client.web_linked ? "привязан" : "нет"}
            </p>
            <p className="hint">
              Один `case_id` в MAX mini-app и веб-кабинете. Admin не дублируется в mini-app.
            </p>
            <div className="row-actions">
              <a href={detail.channels.cabinet_url} target="_blank" rel="noreferrer">Веб-кабинет дела</a>
              <a href={detail.channels.max_bot_url} target="_blank" rel="noreferrer">Бот MAX</a>
              {detail.crm_url && (
                <a href={detail.crm_url} target="_blank" rel="noreferrer">Taganay CRM</a>
              )}
            </div>
            <button type="button" onClick={() => void requestReview()} disabled={busy}>
              Запросить проверку / run
            </button>
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
                <h2>OCR / ИЛС / трудовая / findings</h2>
                <p className="hint">OCR фрагментов: {(detail.ocr_texts ?? []).length}</p>
                <p className="hint">Периоды ИЛС: {(detail.ils_periods ?? []).length} · трудовая: {(detail.labor_periods ?? []).length}</p>
                <ul className="plain-list">
                  {(detail.findings ?? []).length === 0 && <li>Findings пока нет</li>}
                  {(detail.findings ?? []).map((f, idx) => (
                    <li key={`${f.type}-${idx}`}>
                      <strong>{f.type}</strong>
                      <span>{f.detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="panel">
                <h2>Черновик заявления</h2>
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
                    [{item.status}] {item.title}
                  </button>
                  <span className="hint"> · {item.owner}</span>
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
              <h2>Этап pipeline</h2>
              <div className="inline-form">
                <select value={pipelineStatus} onChange={(e) => setPipelineStatus(e.target.value)}>
                  {["intake", "documents_received", "ocr_done", "classified", "extracted", "audited", "draft_ready", "human_review", "completed", "failed"].map((s) => (
                    <option key={s} value={s}>{s}</option>
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
                  SF: {detail.result.success_fee.sf_total} ₽ (lump {detail.result.success_fee.sf_lump} + month {detail.result.success_fee.sf_month})
                </p>
              )}
            </div>
          )}

          {caps?.can_manage_orders && (
            <div className="panel">
              <h2>Создать счёт</h2>
              <form className="inline-form" onSubmit={createOrder}>
                <select value={orderCode} onChange={(e) => setOrderCode(e.target.value as typeof orderCode)}>
                  <option value="DIAG">DIAG</option>
                  <option value="ACCOMP">ACCOMP</option>
                  <option value="SF_LUMP">SF_LUMP</option>
                  <option value="SF_MONTH">SF_MONTH</option>
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
              <p className="hint">Post-payment (SF_*) — только после подтверждения и окна 60+ дней.</p>
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
                  <option value="draft">draft</option>
                  <option value="verified">verified</option>
                  <option value="template">template</option>
                  <option value="rejected">rejected</option>
                </select>
                <button type="submit">Сохранить в feedback</button>
              </form>
            </div>
          )}

          <div className="panel">
            <h2>Сообщения</h2>
            <ul className="messages">
              {messages.map((m) => (
                <li key={m.id}>
                  <span className="meta">{m.author_kind} · {new Date(m.created_at).toLocaleString("ru-RU")}</span>
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
                <strong>{order.package_code}</strong>
                <span>{order.amount_rub} ₽ · {order.status}</span>
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
          <p>Строк для Sheets: {analytics.rows.length}</p>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard.writeText(JSON.stringify(analytics.rows, null, 2));
              setNotice("Whitelist-строки скопированы в буфер.");
            }}
          >
            Копировать JSON для Google Sheets
          </button>
        </section>
      )}

      {view === "roles" && (
        <section className="stack">
          <h1>Роли сотрудников</h1>
          <ul className="plain-list">
            {roles.map((row) => (
              <li key={row.user_id}>{row.user_id} · {row.role}</li>
            ))}
          </ul>
          <form className="inline-form" onSubmit={saveRole}>
            <input
              placeholder="user_id (uuid auth.users)"
              value={newRoleUserId}
              onChange={(e) => setNewRoleUserId(e.target.value)}
              required
            />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value as StaffRole)}>
              <option value="operator">operator</option>
              <option value="expert">expert</option>
              <option value="admin">admin</option>
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
