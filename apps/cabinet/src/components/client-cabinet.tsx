"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

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
  draft: { title?: string; body?: string; needs_human_review?: boolean } | null;
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

type View = "cases" | "case" | "docs" | "payments" | "result";
type AuthChannel = "email" | "phone";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
const SITE_URL = "https://taxi-doroga-dobra.ru";

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
    () => (supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null),
    [],
  );
  const [session, setSession] = useState<Session | null>(null);
  const [authChannel, setAuthChannel] = useState<AuthChannel>("email");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [notice, setNotice] = useState("");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [messages, setMessages] = useState<CaseMessage[]>([]);
  const [messageBody, setMessageBody] = useState("");
  const [consents, setConsents] = useState<ConsentBundle | null>(null);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [result, setResult] = useState<ResultPayload | null>(null);
  const [view, setView] = useState<View>("cases");
  const [busy, setBusy] = useState(false);

  const token = session?.access_token;

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  const loadCases = useCallback(async () => {
    if (!token || !apiBase) return;
    try {
      const rows = await apiFetch<CaseSummary[]>("/api/portal/me/cases", token);
      setCases(rows);
      setNotice("");
    } catch {
      setNotice("Не удалось загрузить дела. Повторите попытку позже.");
    }
  }, [token]);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

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

  async function loadPayments(caseId: string) {
    if (!token) return;
    setBusy(true);
    try {
      const rows = await apiFetch<OrderRow[]>(`/api/portal/cases/${caseId}/orders`, token);
      setOrders(rows);
      setView("payments");
    } catch {
      setNotice("Не удалось загрузить оплаты.");
    } finally {
      setBusy(false);
    }
  }

  async function loadResult(caseId: string) {
    if (!token) return;
    setBusy(true);
    try {
      const payload = await apiFetch<ResultPayload>(`/api/portal/cases/${caseId}/result`, token);
      setResult(payload);
      setView("result");
    } catch {
      setNotice("Не удалось загрузить результат.");
    } finally {
      setBusy(false);
    }
  }

  async function requestOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    setBusy(true);
    try {
      if (authChannel === "email") {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: { shouldCreateUser: true },
        });
        if (error) throw error;
      } else {
        const normalized = phone.replace(/[^\d+]/g, "");
        const { error } = await supabase.auth.signInWithOtp({
          phone: normalized,
          options: { shouldCreateUser: true },
        });
        if (error) throw error;
      }
      setOtpSent(true);
      setNotice("Код отправлен. Введите его ниже.");
    } catch {
      setNotice("Не удалось отправить код. Проверьте данные и попробуйте снова.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true);
    try {
      if (authChannel === "email") {
        const { error } = await supabase.auth.verifyOtp({
          email,
          token: otpCode,
          type: "email",
        });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.verifyOtp({
          phone: phone.replace(/[^\d+]/g, ""),
          token: otpCode,
          type: "sms",
        });
        if (error) throw error;
      }
      setNotice("");
    } catch {
      setNotice("Неверный или просроченный код.");
    } finally {
      setBusy(false);
    }
  }

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

  if (!session) {
    return (
      <main className="auth-layout">
        <section className="card">
          <p className="eyebrow">SFRFR</p>
          <h1>Кабинет клиента</h1>
          <p className="lead">
            Вход по одноразовому коду. Вы увидите только дела, к которым вам выдан доступ.
          </p>
          <div className="tabs" role="tablist">
            <button
              type="button"
              className={authChannel === "email" ? "tab active" : "tab"}
              onClick={() => {
                setAuthChannel("email");
                setOtpSent(false);
              }}
            >
              Email
            </button>
            <button
              type="button"
              className={authChannel === "phone" ? "tab active" : "tab"}
              onClick={() => {
                setAuthChannel("phone");
                setOtpSent(false);
              }}
            >
              Телефон
            </button>
          </div>
          {!otpSent ? (
            <form onSubmit={requestOtp}>
              {authChannel === "email" ? (
                <>
                  <label htmlFor="email">Email</label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    autoComplete="email"
                  />
                </>
              ) : (
                <>
                  <label htmlFor="phone">Телефон</label>
                  <input
                    id="phone"
                    type="tel"
                    placeholder="+79001234567"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    required
                    autoComplete="tel"
                  />
                </>
              )}
              <button type="submit" disabled={busy}>
                Получить код
              </button>
            </form>
          ) : (
            <form onSubmit={verifyOtp}>
              <label htmlFor="otp">Код из {authChannel === "email" ? "письма" : "SMS"}</label>
              <input
                id="otp"
                inputMode="numeric"
                value={otpCode}
                onChange={(event) => setOtpCode(event.target.value)}
                required
                autoComplete="one-time-code"
              />
              <button type="submit" disabled={busy}>
                Войти
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setOtpSent(false);
                  setOtpCode("");
                }}
              >
                Изменить контакт
              </button>
            </form>
          )}
          {notice && <p className="notice">{notice}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-layout">
      <header>
        <div>
          <strong>SFRFR</strong>
          <span>Кабинет клиента</span>
        </div>
        <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
          Выйти
        </button>
      </header>

      <section className="warning" role="note">
        Решение принимает СФР. Результат не гарантирован.
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
              Дел пока нет. Начните обращение через{" "}
              <a href="https://max.ru/id8905998693_1_bot?startapp">MAX</a> или{" "}
              <a href={SITE_URL}>публичный сайт</a>.
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
            Текущий этап: <strong>{labelStatus(detail.pipeline_status)}</strong>
            {" · "}
            {labelStatus(detail.b2c_status)}
          </p>
          <p>
            Ответственный сотрудник:{" "}
            {detail.expert_assigned ? "назначен" : "ещё не назначен"}
          </p>

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
                  </li>
                );
              })}
            </ul>
          )}
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
