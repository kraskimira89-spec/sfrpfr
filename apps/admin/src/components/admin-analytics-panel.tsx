"use client";

import { labelPackage, pipelineStageOptions } from "@/lib/ui-labels";
import { FormEvent, useMemo, useState } from "react";

export type AnalyticsSnapshot = {
  period: { key: string; from: string; to: string };
  filters_applied: {
    channel: string | null;
    package_code: string | null;
    pipeline_status: string | null;
  };
  note: string;
  kpi: {
    total_cases: number;
    new_cases: number;
    in_progress: number;
    paid_diagnostics: number;
    paid_accompaniment: number;
    confirmed_result_changes: number;
    avg_first_response_hours: number | null;
    median_first_response_hours: number | null;
    sla_overdue: number;
    no_next_action: number;
    no_channel: number;
    no_expert: number;
    waiting_on_staff: number;
  };
  funnel: Array<{
    key: string;
    label: string;
    count: number;
    conversion_from_previous_pct: number | null;
    registry_filter: Record<string, string>;
  }>;
  channels: Array<{
    channel: string;
    label: string;
    count: number;
    share_pct: number | null;
    with_expert: number;
    conflicts: number;
    avg_response_hours: number | null;
    overdue_sla: number;
    registry_filter: Record<string, string>;
    alert: boolean;
  }>;
  topics: Array<{ topic: string; count: number; share_pct: number | null }>;
  risks: Array<{
    key: string;
    label: string;
    count: number;
    registry_filter: Record<string, string>;
  }>;
  finance: {
    paid_diagnostics: number;
    paid_accompaniment: number;
    pending_invoices: number;
    pending_amount_rub: number;
    paid_orders_count: number;
    paid_amount_rub: number;
    avg_check_rub: number | null;
    diag_to_service_conversion_pct: number | null;
  } | null;
  export_row_count: number;
  suppress_small_groups: boolean;
};

type AnalyticsFilters = {
  period: string;
  dateFrom: string;
  dateTo: string;
  channel: string;
  packageCode: string;
  pipelineStatus: string;
};

type RegistryFilter = Partial<Record<"queue" | "preferred_channel" | "pipeline_status", string>>;

const PERIOD_OPTIONS = [
  { id: "today", label: "Сегодня" },
  { id: "7d", label: "7 дней" },
  { id: "30d", label: "30 дней" },
  { id: "month", label: "Текущий месяц" },
  { id: "prev_month", label: "Прошлый месяц" },
  { id: "custom", label: "Произвольный" },
];

const CHANNEL_OPTIONS = [
  { id: "", label: "Все каналы" },
  { id: "max_miniapp", label: "MAX mini-app" },
  { id: "web_cabinet", label: "Личный кабинет сайта" },
  { id: "site", label: "Сайт" },
  { id: "phone", label: "Телефон" },
  { id: "email", label: "E-mail" },
  { id: "unset", label: "Канал не определён" },
];

const PACKAGE_OPTIONS = [
  { id: "", label: "Все услуги" },
  { id: "DIAG", label: labelPackage("DIAG") },
  { id: "ACCOMP", label: labelPackage("ACCOMP") },
  { id: "SF_LUMP", label: labelPackage("SF_LUMP") },
  { id: "SF_MONTH", label: labelPackage("SF_MONTH") },
];

function formatHours(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 1) return `${Math.round(value * 60)} мин`;
  return `${value.toFixed(1)} ч`;
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value}%`;
}

function formatRub(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value).toLocaleString("ru-RU")} ₽`;
}

function barWidth(count: number, max: number): string {
  if (max <= 0) return "0%";
  return `${Math.max(8, Math.round((count / max) * 100))}%`;
}

function buildQuery(filters: AnalyticsFilters): string {
  const params = new URLSearchParams();
  params.set("period", filters.period);
  if (filters.period === "custom") {
    if (filters.dateFrom) params.set("date_from", filters.dateFrom);
    if (filters.dateTo) params.set("date_to", filters.dateTo);
  }
  if (filters.channel) params.set("channel", filters.channel);
  if (filters.packageCode) params.set("package_code", filters.packageCode);
  if (filters.pipelineStatus) params.set("pipeline_status", filters.pipelineStatus);
  return params.toString();
}

export function AdminAnalyticsPanel({
  data,
  filters,
  onFiltersChange,
  onReload,
  onOpenRegistry,
  showFinance,
  apiBase,
  token,
  busy,
  onNotice,
}: {
  data: AnalyticsSnapshot;
  filters: AnalyticsFilters;
  onFiltersChange: (next: AnalyticsFilters) => void;
  onReload: () => void;
  onOpenRegistry: (filter: RegistryFilter) => void;
  showFinance: boolean;
  apiBase: string;
  token: string;
  busy: boolean;
  onNotice: (message: string) => void;
}) {
  const [exportOpen, setExportOpen] = useState(false);
  const maxChannelCount = useMemo(
    () => Math.max(1, ...data.channels.map((row) => row.count)),
    [data.channels],
  );
  const pipelineOptions = useMemo(
    () => [{ value: "", label: "Все этапы" }, ...pipelineStageOptions()],
    [],
  );

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    onReload();
  }

  async function downloadExport(format: "csv" | "json") {
    const qs = buildQuery(filters);
    const response = await fetch(
      `${apiBase}/api/portal/admin/analytics/export?${qs}&format=${format}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      onNotice("Не удалось выгрузить данные.");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = format === "csv" ? "sfrfr-analytics.csv" : "sfrfr-analytics.json";
    anchor.click();
    URL.revokeObjectURL(url);
    onNotice(format === "csv" ? "CSV скачан." : "JSON скачан.");
  }

  async function copyJsonExport() {
    const qs = buildQuery(filters);
    const response = await fetch(
      `${apiBase}/api/portal/admin/analytics/export?${qs}&format=json`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      onNotice("Не удалось скопировать JSON.");
      return;
    }
    const text = await response.text();
    await navigator.clipboard.writeText(text);
    onNotice("Обезличенный JSON скопирован.");
  }

  const kpiCards = [
    {
      label: "Всего дел",
      value: data.kpi.total_cases,
      filter: {},
    },
    {
      label: "Новые обращения",
      value: data.kpi.new_cases,
      filter: { queue: "new" },
    },
    {
      label: "В работе",
      value: data.kpi.in_progress,
      filter: { queue: "active" },
    },
    {
      label: "Среднее время первого ответа",
      value: formatHours(data.kpi.avg_first_response_hours),
      filter: { queue: "reply" },
      isText: true,
    },
    {
      label: "Медиана первого ответа",
      value: formatHours(data.kpi.median_first_response_hours),
      filter: { queue: "reply" },
      isText: true,
    },
    {
      label: "Просрочено SLA",
      value: data.kpi.sla_overdue,
      filter: { queue: "overdue" },
      risk: data.kpi.sla_overdue > 0,
    },
    {
      label: "Без следующего действия",
      value: data.kpi.no_next_action,
      filter: { queue: "reply" },
    },
    {
      label: "Канал не определён",
      value: data.kpi.no_channel,
      filter: { preferred_channel: "unset" },
      risk: data.kpi.no_channel > 0,
    },
    {
      label: "Без ответственного",
      value: data.kpi.no_expert,
      filter: { queue: "active" },
      risk: data.kpi.no_expert > 0,
    },
  ];

  return (
    <section className="stack analytics-panel">
      <div>
        <h1>Аналитика</h1>
        <p className="hint">{data.note}</p>
      </div>

      <form className="analytics-filters panel" onSubmit={applyFilters}>
        <label>
          Период
          <select
            value={filters.period}
            onChange={(e) => onFiltersChange({ ...filters, period: e.target.value })}
          >
            {PERIOD_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {filters.period === "custom" && (
          <>
            <label>
              С
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => onFiltersChange({ ...filters, dateFrom: e.target.value })}
              />
            </label>
            <label>
              По
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) => onFiltersChange({ ...filters, dateTo: e.target.value })}
              />
            </label>
          </>
        )}
        <label>
          Канал
          <select
            value={filters.channel}
            onChange={(e) => onFiltersChange({ ...filters, channel: e.target.value })}
          >
            {CHANNEL_OPTIONS.map((option) => (
              <option key={option.id || "all"} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Услуга
          <select
            value={filters.packageCode}
            onChange={(e) => onFiltersChange({ ...filters, packageCode: e.target.value })}
          >
            {PACKAGE_OPTIONS.map((option) => (
              <option key={option.id || "all"} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Этап дела
          <select
            value={filters.pipelineStatus}
            onChange={(e) => onFiltersChange({ ...filters, pipelineStatus: e.target.value })}
          >
            {pipelineOptions.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy}>
          Обновить
        </button>
      </form>

      <div className="metrics">
        {kpiCards.map((card) => (
          <button
            key={card.label}
            type="button"
            className={`metric-card ${card.risk ? "metric-card--risk" : ""}`}
            onClick={() => onOpenRegistry(card.filter)}
          >
            <span>{card.label}</span>
            <strong>{card.isText ? card.value : String(card.value)}</strong>
          </button>
        ))}
      </div>

      <div className="panel">
        <h2>Воронка обращений</h2>
        {data.suppress_small_groups && (
          <p className="hint">Мало дел в выборке — детальные срезы могут быть скрыты.</p>
        )}
        <div className="funnel-grid">
          {data.funnel.map((step) => (
            <article key={step.key} className="funnel-step">
              <span>{step.label}</span>
              <strong>{step.count}</strong>
              {step.key !== "lead" && (
                <em>конверсия {formatPct(step.conversion_from_previous_pct)}</em>
              )}
              <button type="button" className="linkish" onClick={() => onOpenRegistry(step.registry_filter)}>
                Открыть дела
              </button>
            </article>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>Источники обращений</h2>
        <div className="channel-bars">
          {data.channels.map((row) => (
            <div key={row.channel} className={`channel-row ${row.alert ? "channel-row--alert" : ""}`}>
              <div className="channel-row-head">
                <strong>{row.label}</strong>
                <span>
                  {row.count} · {formatPct(row.share_pct)}
                </span>
              </div>
              <div className="channel-bar-track">
                <div className="channel-bar-fill" style={{ width: barWidth(row.count, maxChannelCount) }} />
              </div>
              <p className="hint">
                Ответственный: {row.with_expert} · SLA просрочено: {row.overdue_sla} · конфликты: {row.conflicts}
              </p>
              {row.alert && (
                <button type="button" onClick={() => onOpenRegistry(row.registry_filter)}>
                  Разобрать {row.count} {row.count === 1 ? "дело" : "дела"}
                </button>
              )}
            </div>
          ))}
        </div>
        <table className="queue-table analytics-table">
          <thead>
            <tr>
              <th>Канал</th>
              <th>Дел</th>
              <th>Доля</th>
              <th>Ответственный</th>
              <th>SLA</th>
              <th>Проблемы</th>
            </tr>
          </thead>
          <tbody>
            {data.channels.map((row) => (
              <tr key={`table-${row.channel}`}>
                <td>{row.label}</td>
                <td>{row.count}</td>
                <td>{formatPct(row.share_pct)}</td>
                <td>{row.with_expert}</td>
                <td>{row.overdue_sla}</td>
                <td>
                  {row.conflicts > 0 ? `конфликты: ${row.conflicts}` : row.alert ? "Нужно заполнить" : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.risks.length > 0 && (
        <div className="panel">
          <h2>Операционные риски</h2>
          <div className="chip-row">
            {data.risks.map((risk) => (
              <button
                key={risk.key}
                type="button"
                className="chip"
                onClick={() => onOpenRegistry(risk.registry_filter)}
              >
                {risk.label}: {risk.count}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="panel">
        <h2>Темы обращений</h2>
        {data.topics.length === 0 ? (
          <p className="hint">Нет данных за выбранный период.</p>
        ) : (
          <ul className="plain-list topic-list">
            {data.topics.map((row) => (
              <li key={row.topic}>
                <strong>{row.topic}</strong>
                <span>
                  {row.count} · {formatPct(row.share_pct)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showFinance && data.finance && (
        <div className="panel">
          <h2>Услуги и финансы</h2>
          <div className="metrics">
            <article>
              <span>Оплачено диагностик</span>
              <strong>{data.finance.paid_diagnostics}</strong>
            </article>
            <article>
              <span>Оплачено сопровождений</span>
              <strong>{data.finance.paid_accompaniment}</strong>
            </article>
            <article>
              <span>Счета к оплате</span>
              <strong>
                {data.finance.pending_invoices} · {formatRub(data.finance.pending_amount_rub)}
              </strong>
            </article>
            <article>
              <span>Оплачено заказов</span>
              <strong>
                {data.finance.paid_orders_count} · {formatRub(data.finance.paid_amount_rub)}
              </strong>
            </article>
            <article>
              <span>Средний чек</span>
              <strong>{formatRub(data.finance.avg_check_rub)}</strong>
            </article>
            <article>
              <span>Конверсия диагностика → сопровождение</span>
              <strong>{formatPct(data.finance.diag_to_service_conversion_pct)}</strong>
            </article>
          </div>
        </div>
      )}

      <div className="panel analytics-export">
        <button type="button" className="ghost analytics-export-toggle" onClick={() => setExportOpen((v) => !v)}>
          {exportOpen ? "▾" : "▸"} Экспорт обезличенных данных
        </button>
        {exportOpen && (
          <div className="stack">
            <p className="hint">
              Выгрузка не содержит ФИО, телефоны, e-mail, СНИЛС, файлы, текст документов и сообщений.
              Перед передачей данных третьим лицам убедитесь, что цель и состав выгрузки соответствуют
              внутренним правилам обработки данных.
            </p>
            <p className="hint">Строк в выборке: {data.export_row_count}</p>
            <div className="inline-form">
              <button type="button" disabled={busy} onClick={() => void downloadExport("csv")}>
                Скачать CSV
              </button>
              <button type="button" disabled={busy} onClick={() => void downloadExport("json")}>
                Скачать JSON
              </button>
              <button type="button" disabled={busy} onClick={() => void copyJsonExport()}>
                Скопировать JSON
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
