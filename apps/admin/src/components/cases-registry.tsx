"use client";

import { humanCaseStage, labelB2c, labelPipeline } from "@/lib/ui-labels";
import { useMemo, useState } from "react";

export type RegistryCase = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  client_name: string | null;
  client_phone: string | null;
  expert_user_id: string | null;
  preferred_channel: string;
  max_linked: boolean;
  web_linked: boolean;
  next_action?: string | null;
  next_action_at?: string | null;
  waiting_on?: string | null;
  priority?: string | null;
  deadline_status?: string | null;
  is_test?: boolean;
  last_event?: string | null;
  silent_days?: number;
};

const QUEUES: Array<{ id: string; label: string }> = [
  { id: "active", label: "Все активные" },
  { id: "mine", label: "Мои" },
  { id: "new", label: "Новые" },
  { id: "reply", label: "Требуют ответа" },
  { id: "today", label: "На сегодня" },
  { id: "overdue", label: "Просроченные" },
  { id: "docs", label: "Ждём документы" },
  { id: "payment", label: "Ждём оплату" },
  { id: "noconsent", label: "Без согласия" },
  { id: "conflicts", label: "Конфликты" },
  { id: "test", label: "Тестовые" },
];

const PAGE_SIZE = 40;

function caseCatalogLabel(caseId: string): string {
  const hex = String(caseId || "").replace(/-/g, "").slice(-5);
  const n = Number.parseInt(hex, 16);
  if (!Number.isFinite(n) || n <= 0) return "—";
  return `ПС-${String(n).padStart(6, "0")}`;
}

function formatRelative(value: string | null | undefined): string {
  if (!value) return "Нет срока";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "Нет срока";
  const now = Date.now();
  const diff = dt.getTime() - now;
  const abs = Math.abs(diff);
  const mins = Math.round(abs / 60000);
  if (mins < 60) {
    return diff < 0 ? `${mins} мин назад` : `через ${mins} мин`;
  }
  const hours = Math.round(mins / 60);
  if (hours < 36) {
    return diff < 0 ? `${hours} ч назад` : `сегодня, ${dt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return dt.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function tone(item: RegistryCase): string {
  if (item.deadline_status === "overdue" || item.priority === "urgent") return "overdue";
  if (item.deadline_status === "today" || item.priority === "today") return "today";
  if (item.waiting_on === "client" || item.waiting_on === "archive" || item.waiting_on === "sfr") {
    return "waiting";
  }
  return "ok";
}

function toneLabel(item: RegistryCase): string {
  const t = tone(item);
  if (t === "overdue") return "Просрочено";
  if (t === "today") return "Сегодня";
  if (t === "waiting") return "Ожидание";
  return "Без срока";
}

export function CasesRegistry({
  cases,
  meUserId,
  meRole,
  q,
  onQ,
  filterPipeline,
  onFilterPipeline,
  filterChannel,
  onFilterChannel,
  filterPackage,
  onFilterPackage,
  packageOptions,
  pipelineOptions,
  queue,
  onQueue,
  busy,
  loading,
  onSearch,
  onPreview,
  onOpen,
  onWriteMax,
  onTake,
  onSuggest,
  onRequestDocs,
  onMarkTest,
  preview,
  previewLoading,
}: {
  cases: RegistryCase[];
  meUserId: string;
  meRole: string | null;
  q: string;
  onQ: (v: string) => void;
  filterPipeline: string;
  onFilterPipeline: (v: string) => void;
  filterChannel: string;
  onFilterChannel: (v: string) => void;
  filterPackage: string;
  onFilterPackage: (v: string) => void;
  packageOptions: Array<{ value: string; label: string }>;
  pipelineOptions: Array<{ value: string; label: string }>;
  queue: string;
  onQueue: (v: string) => void;
  busy: boolean;
  loading: boolean;
  onSearch: () => void;
  onPreview: (id: string) => void;
  onOpen: (id: string) => void;
  onWriteMax: (id: string) => void;
  onTake: (id: string) => void;
  onSuggest: (id: string) => void;
  onRequestDocs: (id: string) => void;
  onMarkTest: (id: string, isTest: boolean) => void;
  preview: {
    id: string;
    stage: string;
    next_action?: string | null;
    next_action_at?: string | null;
    waiting_on?: string | null;
    last_event?: string | null;
    max_linked?: boolean;
    consent?: boolean;
    docs?: Array<{ label: string; done: boolean }>;
    history?: Array<{ at: string; text: string }>;
  } | null;
  previewLoading: boolean;
}) {
  const [page, setPage] = useState(0);
  const [menuId, setMenuId] = useState<string | null>(null);

  const counts = useMemo(() => {
    const live = cases.filter((c) => !c.is_test);
    return {
      active: live.filter((c) => c.pipeline_status !== "completed" && c.b2c_status !== "closed").length,
      reply: live.filter((c) => c.waiting_on === "staff").length,
      overdue: live.filter((c) => c.deadline_status === "overdue").length,
      docs: live.filter((c) => c.waiting_on === "client" || c.waiting_on === "archive").length,
    };
  }, [cases]);

  const visible = cases.slice(0, (page + 1) * PAGE_SIZE);

  return (
    <section className="stack registry">
      <div className="registry-head">
        <h1>Реестр дел</h1>
      </div>
      <form
        className="filters registry-filters"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(0);
          onSearch();
        }}
      >
        <input
          placeholder="Поиск клиента, ID, телефона"
          value={q}
          onChange={(e) => onQ(e.target.value)}
        />
        <select value={filterPipeline} onChange={(e) => onFilterPipeline(e.target.value)}>
          <option value="">Все этапы</option>
          {pipelineOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select value={filterChannel} onChange={(e) => onFilterChannel(e.target.value)}>
          <option value="">Все каналы</option>
          <option value="max_miniapp">MAX</option>
          <option value="web_cabinet">Веб</option>
          <option value="unset">Не выбран</option>
        </select>
        <select value={filterPackage} onChange={(e) => onFilterPackage(e.target.value)}>
          <option value="">Все услуги</option>
          {packageOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <button type="submit">Найти</button>
      </form>

      <div className="chip-row registry-queues">
        {QUEUES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={queue === item.id ? "chip active" : "chip"}
            onClick={() => {
              setPage(0);
              onQueue(item.id);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <p className="registry-stats hint">
        Активных: {counts.active} · Нужен ответ: {counts.reply} · Просрочено: {counts.overdue} · Ждём документы: {counts.docs}
        {queue !== "test" ? " · Тестовые скрыты" : " · Показаны тестовые"}
      </p>

      <div className="registry-layout">
        <div className="registry-main">
          {loading ? (
            <div className="skeleton-stack" aria-busy="true">
              <div className="skeleton" />
              <div className="skeleton" />
              <div className="skeleton" />
            </div>
          ) : visible.length === 0 ? (
            <p className="panel hint">В этой очереди дел нет. Смените фильтр или откройте «Тестовые».</p>
          ) : (
            <>
              <div className="queue-wrap registry-table-wrap">
                <table className="queue-table registry-table">
                  <thead>
                    <tr>
                      <th>!</th>
                      <th>Клиент / дело</th>
                      <th>Этап</th>
                      <th>Каналы</th>
                      <th>Следующий шаг</th>
                      <th>Срок</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((item) => (
                      <tr
                        key={item.id}
                        className={`tone-${tone(item)} ${preview?.id === item.id ? "is-selected" : ""}`}
                        onClick={() => onPreview(item.id)}
                      >
                        <td>
                          <span className={`prio-dot prio-dot--${tone(item)}`} title={toneLabel(item)} />
                          <span className="prio-text">{toneLabel(item)}</span>
                        </td>
                        <td>
                          <strong>{item.client_name ?? "Клиент"} · {caseCatalogLabel(item.id)}</strong>
                        </td>
                        <td>{humanCaseStage(item.pipeline_status, item.b2c_status)}</td>
                        <td>
                          <span className="channel-badges">
                            <span className={item.max_linked ? "badge on" : "badge"} title={item.max_linked ? "MAX привязан" : "MAX нет"}>MAX</span>
                            <span className={item.web_linked ? "badge on" : "badge"} title={item.web_linked ? "Веб-кабинет есть" : "Веб-кабинета нет"}>сайт</span>
                          </span>
                        </td>
                        <td>{item.next_action || "Уточнить ситуацию"}</td>
                        <td>
                          <span className={`deadline deadline--${item.deadline_status || "ok"}`}>
                            {formatRelative(item.next_action_at)}
                          </span>
                        </td>
                        <td>
                          <div className="row-actions" onClick={(e) => e.stopPropagation()}>
                            <button type="button" className="ghost" onClick={() => onOpen(item.id)}>Открыть</button>
                            {item.max_linked && (
                              <button type="button" className="ghost" onClick={() => onWriteMax(item.id)}>Написать</button>
                            )}
                            {item.expert_user_id !== meUserId && (
                              <button type="button" className="ghost" disabled={busy} onClick={() => onTake(item.id)}>В работу</button>
                            )}
                            <button
                              type="button"
                              className="ghost"
                              aria-label="Ещё"
                              onClick={() => setMenuId(menuId === item.id ? null : item.id)}
                            >
                              ⋮
                            </button>
                          </div>
                          {menuId === item.id && (
                            <div className="row-menu" onClick={(e) => e.stopPropagation()}>
                              <button type="button" className="linkish" onClick={() => { onSuggest(item.id); setMenuId(null); }}>
                                Подсказать шаг (DeepSeek)
                              </button>
                              <button type="button" className="linkish" onClick={() => { onRequestDocs(item.id); setMenuId(null); }}>
                                Запросить документы
                              </button>
                              {meRole === "admin" && (
                                <button type="button" className="linkish" onClick={() => { onMarkTest(item.id, !item.is_test); setMenuId(null); }}>
                                  {item.is_test ? "Убрать из тестовых" : "Пометить тестовым"}
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <ul className="registry-cards">
                {visible.map((item) => (
                  <li key={item.id} className={`registry-card tone-${tone(item)}`}>
                    <div className="registry-card__top">
                      <span className={`prio-dot prio-dot--${tone(item)}`} />
                      <strong>{toneLabel(item)}</strong>
                    </div>
                    <button type="button" className="linkish" onClick={() => onOpen(item.id)}>
                      {item.client_name ?? "Клиент"} · {caseCatalogLabel(item.id)}
                    </button>
                    <p>{humanCaseStage(item.pipeline_status, item.b2c_status)}</p>
                    <p>Следующий шаг: {item.next_action || "Уточнить ситуацию"}</p>
                    <p>Срок: {formatRelative(item.next_action_at)}</p>
                    <div className="row-actions">
                      <button type="button" onClick={() => onOpen(item.id)}>Открыть дело</button>
                      {item.max_linked && (
                        <button type="button" className="ghost" onClick={() => onWriteMax(item.id)}>Написать</button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>

              {visible.length < cases.length && (
                <button type="button" className="ghost" onClick={() => setPage((n) => n + 1)}>
                  Показать ещё ({cases.length - visible.length})
                </button>
              )}
            </>
          )}
        </div>

        <aside className="registry-side panel">
          {previewLoading && <p className="hint">Загружаем дело…</p>}
          {!previewLoading && !preview && (
            <p className="hint">Выберите строку — справа откроется краткая карточка без новой вкладки.</p>
          )}
          {preview && (
            <>
              <h2>{caseCatalogLabel(preview.id)}</h2>
              <p><strong>{preview.stage}</strong></p>
              {preview.consent && <p className="badge on">Согласие получено</p>}
              <p className="hint">{preview.last_event}</p>
              <h3>Следующее действие</h3>
              <p>{preview.next_action || "Уточнить ситуацию"}</p>
              <p className="hint">{formatRelative(preview.next_action_at)}</p>
              <div className="row-actions">
                {preview.max_linked && (
                  <button type="button" onClick={() => onWriteMax(preview.id)}>Написать в MAX</button>
                )}
                <button type="button" className="ghost" onClick={() => onOpen(preview.id)}>Открыть полностью</button>
              </div>
              {preview.docs && (
                <>
                  <h3>Документы</h3>
                  <ul className="plain-list">
                    {preview.docs.map((doc) => (
                      <li key={doc.label}>{doc.done ? "✓" : "○"} {doc.label}</li>
                    ))}
                  </ul>
                </>
              )}
              {preview.history && preview.history.length > 0 && (
                <>
                  <h3>История</h3>
                  <ul className="plain-list">
                    {preview.history.slice(0, 5).map((row) => (
                      <li key={row.at + row.text}>{row.at} — {row.text}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </aside>
      </div>
    </section>
  );
}

export function buildPreviewFromSummary(item: RegistryCase): {
  id: string;
  stage: string;
  next_action?: string | null;
  next_action_at?: string | null;
  waiting_on?: string | null;
  last_event?: string | null;
  max_linked?: boolean;
  consent?: boolean;
  docs: Array<{ label: string; done: boolean }>;
} {
  return {
    id: item.id,
    stage: humanCaseStage(item.pipeline_status, item.b2c_status),
    next_action: item.next_action,
    next_action_at: item.next_action_at,
    waiting_on: item.waiting_on,
    last_event: item.last_event,
    max_linked: item.max_linked,
    consent: item.b2c_status !== "lead",
    docs: [
      { label: "Согласие ПДн", done: item.b2c_status !== "lead" },
      { label: "Выписка ИЛС", done: false },
      { label: "Трудовая / сведения о работе", done: false },
      { label: "Справки", done: item.waiting_on !== "archive" },
    ],
  };
}

export { caseCatalogLabel, labelB2c, labelPipeline };
