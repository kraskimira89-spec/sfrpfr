"use client";

import { caseCatalogLabel } from "@/components/cases-registry";
import { labelFinanceStatus } from "@/lib/ui-labels";
import { useMemo, useState } from "react";

export type FinanceKpi = { count: number; amount_rub: number };

export type FinanceOrder = {
  id: string;
  case_id: string;
  invoice_number?: string | null;
  package_code: string;
  service_label?: string | null;
  amount_rub: number;
  status: string;
  finance_status: string;
  due_at?: string | null;
  created_at?: string | null;
  pay_url?: string | null;
  qr_url?: string | null;
  sent_channel?: string | null;
  next_action?: string | null;
  client_name?: string | null;
  is_test?: boolean;
  reminder_draft?: string | null;
  max_linked?: boolean;
  history?: Array<{ at: string; text: string }>;
  payment_purpose?: string;
  cancel_reason?: string | null;
  needs_invoice?: boolean;
};

export type FinanceSnapshot = {
  disclaimer: string;
  payment_purpose: string;
  tariffs: Array<{
    code: string;
    package_code: string | null;
    name: string;
    amount_rub: number;
    includes: string;
    status: string;
    unit?: string;
  }>;
  tariffs_url: string;
  kpis: {
    payable: FinanceKpi;
    overdue: FinanceKpi;
    paid_today: FinanceKpi;
    awaiting_invoice: FinanceKpi;
    refunds: FinanceKpi;
  };
  orders: FinanceOrder[];
  total: number;
  can_manage?: boolean;
};

const QUEUES: Array<{ id: string; label: string; kpi?: keyof FinanceSnapshot["kpis"] }> = [
  { id: "all", label: "Все" },
  { id: "payable", label: "К оплате", kpi: "payable" },
  { id: "overdue", label: "Просрочено", kpi: "overdue" },
  { id: "paid_today", label: "Оплачено сегодня", kpi: "paid_today" },
  { id: "awaiting_invoice", label: "Ожидает счёт", kpi: "awaiting_invoice" },
  { id: "refunds", label: "Возвраты / отмены", kpi: "refunds" },
];

function formatRub(value: number): string {
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(value || 0))} ₽`;
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  const now = Date.now();
  const diff = dt.getTime() - now;
  const days = Math.round(Math.abs(diff) / 86400000);
  if (diff < 0 && days >= 1) return `${days} дн. назад`;
  if (diff < 0) return "сегодня";
  return dt.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function tone(status: string): string {
  if (status === "overdue") return "overdue";
  if (status === "paid") return "ok";
  if (status === "draft" || status === "awaiting_invoice") return "calm";
  if (status === "partially_paid" || status === "reconciliation_error") return "today";
  if (status === "cancelled" || status === "refund") return "muted";
  return "today";
}

export function FinancePanel({
  data,
  loading,
  busy,
  canManage,
  meRole,
  q,
  onQ,
  queue,
  onQueue,
  period,
  onPeriod,
  packageCode,
  onPackageCode,
  includeTest,
  onIncludeTest,
  onSearch,
  onCreate,
  onCreateForCase,
  onOpenCase,
  onCopyLink,
  onSendLink,
  onRemind,
  onMarkPaid,
  onCancel,
  caseFilterActive = false,
  onClearCaseFilter,
}: {
  data: FinanceSnapshot | null;
  loading: boolean;
  busy: boolean;
  canManage: boolean;
  meRole: string | null;
  q: string;
  onQ: (v: string) => void;
  queue: string;
  onQueue: (v: string) => void;
  period: string;
  onPeriod: (v: string) => void;
  packageCode: string;
  onPackageCode: (v: string) => void;
  includeTest: boolean;
  onIncludeTest: (v: boolean) => void;
  onSearch: () => void;
  onCreate: () => void;
  /** Открыть создание счёта сразу для дела (строка «ожидает счёт»). */
  onCreateForCase?: (caseId: string) => void;
  onOpenCase: (caseId: string) => void;
  onCopyLink: (order: FinanceOrder) => void;
  onSendLink: (order: FinanceOrder) => void;
  onRemind: (order: FinanceOrder, sendMax: boolean) => void;
  onMarkPaid: (order: FinanceOrder) => void;
  onCancel: (order: FinanceOrder) => void;
  /** Поиск сужен до дела (переход из реестра). */
  caseFilterActive?: boolean;
  onClearCaseFilter?: () => void;
}) {
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [showTariffs, setShowTariffs] = useState(false);
  const orders = data?.orders ?? [];
  const preview = useMemo(
    () => orders.find((row) => row.id === previewId) ?? null,
    [orders, previewId],
  );
  const kpis = data?.kpis;

  return (
    <section className="stack finance">
      <div className="registry-head finance-head">
        <div>
          <h1>Финансы</h1>
          <p className="lead lead-compact">{data?.disclaimer}</p>
        </div>
        <div className="row-actions">
          {canManage && (
            <button type="button" onClick={onCreate}>Создать счёт</button>
          )}
          {meRole === "admin" && (
            <button type="button" className="ghost" onClick={() => setShowTariffs((v) => !v)}>
              Тарифы
            </button>
          )}
        </div>
      </div>

      <div className="metrics finance-kpis">
        {QUEUES.filter((item) => item.kpi).map((item) => {
          const kpi = item.kpi ? kpis?.[item.kpi] : undefined;
          return (
            <button
              key={item.id}
              type="button"
              className={`metric-card ${queue === item.id ? "is-active" : ""} ${item.id === "overdue" ? "metric-card--risk" : ""}`}
              onClick={() => onQueue(queue === item.id ? "all" : item.id)}
            >
              <span>{item.label}</span>
              <strong>{kpi?.count ?? 0}</strong>
              <em>{formatRub(kpi?.amount_rub ?? 0)}</em>
            </button>
          );
        })}
      </div>

      <form
        className="filters registry-filters"
        onSubmit={(e) => {
          e.preventDefault();
          onSearch();
        }}
      >
        <input
          placeholder="Клиент, ID дела, номер счёта"
          value={q}
          onChange={(e) => onQ(e.target.value)}
        />
        <select value={period} onChange={(e) => onPeriod(e.target.value)}>
          <option value="">Период: все</option>
          <option value="today">Сегодня</option>
          <option value="week">Неделя</option>
          <option value="month">Месяц</option>
        </select>
        <select value={packageCode} onChange={(e) => onPackageCode(e.target.value)}>
          <option value="">Все услуги</option>
          <option value="DIAG">Диагностика</option>
          <option value="ACCOMP">Документы / сопровождение</option>
        </select>
        <label className="hint">
          <input type="checkbox" checked={includeTest} onChange={(e) => onIncludeTest(e.target.checked)} />
          {" "}Тестовые
        </label>
        <button type="submit">Найти</button>
      </form>

      <p className="hint">
        Найдено: {data?.total ?? 0}
        {includeTest ? "" : " · тестовые скрыты"}
        {" · "}
        {data?.payment_purpose}
      </p>
      {caseFilterActive ? (
        <p className="hint">
          Показаны счета / дела по выбранному делу из реестра.
          {onClearCaseFilter ? (
            <>
              {" "}
              <button type="button" className="linkish" onClick={onClearCaseFilter}>
                Сбросить фильтр дела
              </button>
            </>
          ) : null}
        </p>
      ) : (
        <p className="hint">
          Статусы счетов (просрочено, ожидает счёт, возврат) живут здесь. В реестре дел — только сигнал «Оплата», без дублирования этапов сделки.
        </p>
      )}

      {showTariffs && data?.tariffs && (
        <div className="panel finance-tariffs">
          <h2>Тарифы с сайта</h2>
          <p className="hint">
            Источник: <a href={data.tariffs_url} target="_blank" rel="noreferrer">{data.tariffs_url}</a>
          </p>
          <table className="queue-table">
            <thead>
              <tr>
                <th>Услуга</th>
                <th>Стоимость</th>
                <th>Что входит</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {data.tariffs.map((row) => (
                <tr key={row.code}>
                  <td>{row.name}</td>
                  <td>{formatRub(row.amount_rub)}{row.unit ? ` ${row.unit}` : ""}</td>
                  <td>{row.includes}</td>
                  <td>{row.status === "active" ? "Активна" : "По согласованию"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">
            Индивидуальное соглашение (фиксированная сумма) оформляется отдельно, если клиент не готов
            оплатить этап сразу. В интерфейсе нет процентов от ЕДВ или прибавки к пенсии.
          </p>
        </div>
      )}

      <div className="registry-layout">
        <div className="registry-main">
          {loading ? (
            <div className="skeleton-stack" aria-busy="true">
              <div className="skeleton" />
              <div className="skeleton" />
            </div>
          ) : orders.length === 0 ? (
            <p className="panel hint">
              {queue === "awaiting_invoice"
                ? "Нет дел, ожидающих счёт."
                : "В этой очереди счетов нет."}
            </p>
          ) : (
            <>
              <div className="queue-wrap registry-table-wrap">
                <table className="queue-table registry-table">
                  <thead>
                    <tr>
                      <th>Статус</th>
                      <th>Клиент / дело</th>
                      <th>Услуга</th>
                      <th>Сумма</th>
                      <th>Счёт</th>
                      <th>Срок</th>
                      <th>Следующее действие</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((row) => {
                      const placeholder = Boolean(row.needs_invoice);
                      return (
                      <tr
                        key={row.id}
                        className={`sla-stripe sla-stripe--${tone(row.finance_status)} ${preview?.id === row.id ? "is-selected" : ""}`}
                        onClick={() => setPreviewId(row.id)}
                      >
                        <td>
                          <span className={`prio-dot prio-dot--${tone(row.finance_status)}`} />
                          {labelFinanceStatus(row.finance_status)}
                        </td>
                        <td>
                          <strong>{row.client_name ?? "Клиент"} · {caseCatalogLabel(row.case_id)}</strong>
                        </td>
                        <td>{row.service_label}</td>
                        <td>{placeholder ? "—" : formatRub(row.amount_rub)}</td>
                        <td>{row.invoice_number || "—"}</td>
                        <td>{formatWhen(row.due_at)}</td>
                        <td>{row.next_action}</td>
                        <td>
                          <div className="row-actions" onClick={(e) => e.stopPropagation()}>
                            <button type="button" className="ghost" onClick={() => onOpenCase(row.case_id)}>Открыть</button>
                            {placeholder && canManage && onCreateForCase && (
                              <button type="button" className="ghost" disabled={busy} onClick={() => onCreateForCase(row.case_id)}>
                                Выставить счёт
                              </button>
                            )}
                            {!placeholder && row.finance_status !== "paid" && row.finance_status !== "cancelled" && (
                              <>
                                <button type="button" className="ghost" disabled={busy} onClick={() => onCopyLink(row)}>Ссылка</button>
                                {row.max_linked && (
                                  <button type="button" className="ghost" disabled={busy} onClick={() => onSendLink(row)}>В MAX</button>
                                )}
                              </>
                            )}
                            {row.finance_status === "overdue" && (
                              <button type="button" className="ghost" disabled={busy} onClick={() => onRemind(row, Boolean(row.max_linked))}>Напомнить</button>
                            )}
                          </div>
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <ul className="registry-cards">
                {orders.map((row) => {
                  const placeholder = Boolean(row.needs_invoice);
                  return (
                  <li key={row.id} className={`registry-card sla-stripe sla-stripe--${tone(row.finance_status)}`}>
                    <strong>{labelFinanceStatus(row.finance_status)}</strong>
                    <p>{row.client_name ?? "Клиент"} · {caseCatalogLabel(row.case_id)}</p>
                    <p>{row.service_label} · {placeholder ? "—" : formatRub(row.amount_rub)}</p>
                    <p>Срок: {formatWhen(row.due_at)}</p>
                    <p>{row.next_action}</p>
                    <div className="row-actions">
                      <button type="button" onClick={() => onOpenCase(row.case_id)}>Открыть дело</button>
                      {placeholder && canManage && onCreateForCase && (
                        <button type="button" className="ghost" disabled={busy} onClick={() => onCreateForCase(row.case_id)}>
                          Выставить счёт
                        </button>
                      )}
                      {!placeholder && row.finance_status !== "paid" && (
                        <>
                          <button type="button" className="ghost" onClick={() => onCopyLink(row)}>Ссылка</button>
                          {row.max_linked && (
                            <button type="button" className="ghost" disabled={busy} onClick={() => onSendLink(row)}>В MAX</button>
                          )}
                        </>
                      )}
                    </div>
                  </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
        <aside className="registry-side panel">
          {!preview && <p className="hint">Выберите счёт — справа откроется карточка оплаты.</p>}
          {preview && (
            <>
              <h2>
                {preview.needs_invoice
                  ? `Дело · ${caseCatalogLabel(preview.case_id)}`
                  : `${preview.invoice_number} · ${caseCatalogLabel(preview.case_id)}`}
              </h2>
              <p><strong>{preview.client_name ?? "Клиент"}</strong></p>
              <p>{preview.service_label}</p>
              <p>
                {preview.needs_invoice ? "—" : formatRub(preview.amount_rub)}
                {" · "}
                {labelFinanceStatus(preview.finance_status)}
              </p>
              <p className="hint">{preview.payment_purpose}</p>
              {!preview.needs_invoice && (
                <p className="hint">Срок: {formatWhen(preview.due_at)}</p>
              )}
              {preview.qr_url && preview.finance_status !== "paid" && preview.finance_status !== "cancelled" && (
                <img
                  className="pay-qr"
                  src={preview.qr_url}
                  alt="QR на оплату ЮKassa"
                  width={180}
                  height={180}
                />
              )}
              {preview.pay_url && (
                <p className="hint"><a href={preview.pay_url} target="_blank" rel="noreferrer">Открыть ссылку оплаты</a></p>
              )}
              <div className="row-actions">
                <button type="button" className="ghost" onClick={() => onOpenCase(preview.case_id)}>Открыть дело</button>
                {preview.needs_invoice && canManage && onCreateForCase && (
                  <button type="button" disabled={busy} onClick={() => onCreateForCase(preview.case_id)}>
                    Выставить счёт
                  </button>
                )}
                {!preview.needs_invoice && preview.finance_status !== "paid" && preview.finance_status !== "cancelled" && (
                  <button type="button" disabled={busy} onClick={() => onCopyLink(preview)}>Скопировать ссылку</button>
                )}
                {!preview.needs_invoice && preview.max_linked && preview.finance_status !== "paid" && preview.finance_status !== "cancelled" && (
                  <button type="button" disabled={busy} onClick={() => onSendLink(preview)}>
                    Отправить в MAX
                  </button>
                )}
                {!preview.needs_invoice && preview.max_linked && preview.finance_status !== "paid" && (
                  <button type="button" className="ghost" disabled={busy} onClick={() => onRemind(preview, true)}>
                    Напомнить в MAX
                  </button>
                )}
                {canManage && !preview.needs_invoice && preview.finance_status !== "paid" && preview.finance_status !== "cancelled" && (
                  <>
                    <button type="button" className="ghost" disabled={busy} onClick={() => onMarkPaid(preview)}>
                      Отметить оплату
                    </button>
                    <button type="button" className="ghost" disabled={busy} onClick={() => onCancel(preview)}>
                      Отменить счёт
                    </button>
                  </>
                )}
              </div>
              {preview.history && preview.history.length > 0 && (
                <>
                  <h3>История</h3>
                  <ul className="plain-list">
                    {preview.history.map((row) => (
                      <li key={`${row.at}-${row.text}`}>{formatWhen(row.at)} — {row.text}</li>
                    ))}
                  </ul>
                </>
              )}
              {preview.reminder_draft && (
                <p className="hint">Черновик напоминания: {preview.reminder_draft}</p>
              )}
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
