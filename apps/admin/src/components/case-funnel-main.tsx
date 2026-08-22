"use client";

import {
  DOC_REQUEST_ILS,
  DOC_REQUEST_LABOR,
  PLAN_READY_CHAT,
  SERVICE_DESCRIPTION_CHAT,
  deriveFunnel,
  primaryCtaLabel,
  slaHint,
  type FunnelStageId,
  type FunnelStageState,
} from "@/lib/case-funnel";
import {
  humanCaseStage,
  labelChecklistOwner,
  labelChecklistStatus,
  labelFeedbackQuality,
  labelPackage,
  pipelineStageOptions,
} from "@/lib/ui-labels";
import { caseCatalogLabel } from "@/components/cases-registry";
import { FormEvent, useEffect, useState, type ReactNode } from "react";

type Caps = {
  can_edit_pipeline: boolean;
  can_edit_checklist: boolean;
  can_confirm_result: boolean;
  can_manage_orders: boolean;
  can_view_ocr: boolean;
  can_knowledge_feedback: boolean;
};

type Detail = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  consent_accepted?: boolean;
  expert_user_id?: string | null;
  warning: string;
  next_action?: string | null;
  next_action_at?: string | null;
  waiting_on?: string | null;
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
    created_at?: string;
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
    max_business_url?: string | null;
  };
  representatives?: {
    user_id: string;
    email?: string | null;
    full_name?: string | null;
  }[];
  crm_url?: string | null;
  meeting_url?: string | null;
  orders?: { id: string; package_code: string; amount_rub: number; status: string }[];
  orders_summary?: { package_code: string; status: string }[];
  audit: { action: string; at: string }[];
  role_capabilities: Caps;
};

export type StepChatMessage = {
  kind: "full" | "short" | "cabinet_howto";
  text: string;
};

const CHANNEL_LABELS: Record<string, string> = {
  max_miniapp: "MAX",
  web_cabinet: "Веб-кабинет",
  unset: "не выбран",
};

const WAITING_LABELS: Record<string, string> = {
  staff: "Сотрудник",
  client: "Клиент",
  archive: "Архив",
  sfr: "СФР",
  payment: "Оплата",
  none: "—",
};

const SHOW_ALL_KEY = "sfrfr.case.showAllStages";

const KIND_LABEL: Record<StepChatMessage["kind"], string> = {
  full: "Полный запрос",
  short: "Короткое напоминание",
  cabinet_howto: "Инструкция по кабинету",
};

function StageMark({ state }: { state: FunnelStageState }) {
  if (state === "done") return <span className="funnel-mark funnel-mark--done">✓</span>;
  if (state === "current") return <span className="funnel-mark funnel-mark--current">→</span>;
  if (state === "overdue") return <span className="funnel-mark funnel-mark--overdue">!</span>;
  if (state === "waiting") return <span className="funnel-mark funnel-mark--waiting">…</span>;
  if (state === "blocked") return <span className="funnel-mark funnel-mark--blocked">✕</span>;
  return <span className="funnel-mark">○</span>;
}

function StageShell({
  id,
  title,
  state,
  reason,
  expanded,
  forceShow,
  onToggle,
  children,
  accent,
}: {
  id: string;
  title: string;
  state: FunnelStageState;
  reason: string;
  expanded: boolean;
  forceShow: boolean;
  onToggle: () => void;
  children: ReactNode;
  accent?: boolean;
}) {
  const showBody = expanded || forceShow;
  if (state === "done" && !forceShow) {
    return (
      <div id={id} className="panel funnel-stage funnel-stage--done-compact">
        <button type="button" className="funnel-stage-toggle" onClick={onToggle} title={reason}>
          <StageMark state="done" />
          <strong>{title}</strong>
          <span className="hint">готово</span>
        </button>
      </div>
    );
  }
  if (!showBody) {
    return (
      <div id={id} className={`panel funnel-stage funnel-stage--${state}`}>
        <button type="button" className="funnel-stage-toggle" onClick={onToggle} title={reason}>
          <StageMark state={state} />
          <strong>{title}</strong>
          <span className="hint">{reason}</span>
        </button>
      </div>
    );
  }
  return (
    <div id={id} className={`panel funnel-stage funnel-stage--${state}${accent ? " accent" : ""}`}>
      <button type="button" className="funnel-stage-toggle" onClick={onToggle} title={reason}>
        <StageMark state={state} />
        <strong>{title}</strong>
        {!expanded && forceShow ? <span className="hint">просмотр</span> : null}
      </button>
      <div className="funnel-stage-body">{children}</div>
    </div>
  );
}

function docSourceLabel(doc: Detail["documents"][0]): string {
  const t = `${doc.doc_type || ""} ${doc.storage_path || ""}`.toLowerCase();
  if (/ils|илс|сзи/.test(t)) return "ИЛС";
  if (/labor|труд|employment/.test(t)) return "Трудовая";
  return doc.doc_type || "файл";
}

export function CaseFunnelMain({
  detail,
  meUserId,
  busy,
  nextActionText,
  nextActionAt,
  waitingOn,
  pipelineStatus,
  checklistTitle,
  beforeRub,
  afterRub,
  lumpRub,
  sfrReceived,
  orderCode,
  orderAmount,
  feedbackText,
  feedbackQuality,
  repEmail,
  stepHint,
  stepMessages,
  onBack,
  onNextActionText,
  onNextActionAt,
  onWaitingOn,
  onSaveNextAction,
  onSuggestStep,
  onApplyChatMessage,
  onDismissHint,
  onTake,
  onFocusMax,
  onRequestReview,
  onCreateTelemost,
  onSendEmail,
  onOpenSigned,
  onToggleChecklist,
  onAddChecklist,
  onChecklistTitle,
  onPipelineStatus,
  onSavePipeline,
  onConfirmResult,
  onBeforeRub,
  onAfterRub,
  onLumpRub,
  onSfrReceived,
  onOrderCode,
  onOrderAmount,
  onCreateOrder,
  onRecordServiceConsent,
  onFeedbackText,
  onFeedbackQuality,
  onSendFeedback,
  onRepEmail,
  onAddRepresentative,
  onRemoveRepresentative,
}: {
  detail: Detail;
  meUserId: string | null;
  busy: boolean;
  nextActionText: string;
  nextActionAt: string;
  waitingOn: string;
  pipelineStatus: string;
  checklistTitle: string;
  beforeRub: string;
  afterRub: string;
  lumpRub: string;
  sfrReceived: boolean;
  orderCode: "DIAG" | "ACCOMP" | "SF_LUMP" | "SF_MONTH";
  orderAmount: string;
  feedbackText: string;
  feedbackQuality: string;
  repEmail: string;
  stepHint: { action: string; reason: string; source: string } | null;
  stepMessages: StepChatMessage[];
  onBack: () => void;
  onNextActionText: (v: string) => void;
  onNextActionAt: (v: string) => void;
  onWaitingOn: (v: string) => void;
  onSaveNextAction: () => void;
  onSuggestStep: () => void;
  onApplyChatMessage: (text: string, opts?: { confirmAssign?: boolean }) => void;
  onDismissHint: () => void;
  onTake: () => void;
  onFocusMax: () => void;
  onRequestReview: () => void;
  onCreateTelemost: () => void;
  onSendEmail: () => void;
  onOpenSigned: (docId: string) => void;
  onToggleChecklist: (id: string, status: string) => void;
  onAddChecklist: (e: FormEvent) => void;
  onChecklistTitle: (v: string) => void;
  onPipelineStatus: (v: string) => void;
  onSavePipeline: () => void;
  onConfirmResult: (e: FormEvent) => void;
  onBeforeRub: (v: string) => void;
  onAfterRub: (v: string) => void;
  onLumpRub: (v: string) => void;
  onSfrReceived: (v: boolean) => void;
  onOrderCode: (v: "DIAG" | "ACCOMP" | "SF_LUMP" | "SF_MONTH") => void;
  onOrderAmount: (v: string) => void;
  onCreateOrder: (e: FormEvent) => void;
  onRecordServiceConsent: () => void;
  onFeedbackText: (v: string) => void;
  onFeedbackQuality: (v: string) => void;
  onSendFeedback: (e: FormEvent) => void;
  onRepEmail: (v: string) => void;
  onAddRepresentative: (e: FormEvent) => void;
  onRemoveRepresentative: (userId: string) => void;
}) {
  const caps = detail.role_capabilities;
  const funnel = deriveFunnel(detail);
  const current = funnel.current;
  const stageById = Object.fromEntries(funnel.stages.map((s) => [s.id, s])) as Record<
    FunnelStageId,
    (typeof funnel.stages)[0]
  >;
  const stageLabel = humanCaseStage(detail.pipeline_status, detail.b2c_status);
  const assigned =
    detail.expert_user_id === meUserId
      ? "Я"
      : detail.expert_user_id
        ? "Назначен"
        : "Не назначен";
  const cta = primaryCtaLabel(current, funnel.docsReady);
  const docCount = detail.documents.length;
  const auditPreview = detail.audit.slice(0, 5);
  const auditRest = detail.audit.slice(5);

  const [showAll, setShowAll] = useState(false);
  const [manualOpen, setManualOpen] = useState<FunnelStageId | null>(null);
  const [repOpen, setRepOpen] = useState(false);

  useEffect(() => {
    try {
      setShowAll(localStorage.getItem(SHOW_ALL_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    setManualOpen(null);
  }, [detail.id, current]);

  function setShowAllPersist(v: boolean) {
    setShowAll(v);
    try {
      localStorage.setItem(SHOW_ALL_KEY, v ? "1" : "0");
    } catch {
      /* ignore */
    }
  }

  function isExpanded(id: FunnelStageId): boolean {
    if (showAll) return true;
    if (manualOpen === id) return true;
    return id === current;
  }

  function scrollStage(id: FunnelStageId) {
    setManualOpen(id);
    requestAnimationFrame(() => {
      document.getElementById(`funnel-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function canAct(id: FunnelStageId): boolean {
    return Boolean(stageById[id]?.canAct);
  }

  function applyTemplate(text: string) {
    if (!detail.expert_user_id && meUserId) {
      onApplyChatMessage(text, { confirmAssign: true });
      return;
    }
    onApplyChatMessage(text);
  }

  function runPrimaryCta() {
    if (!canAct(current)) return;
    if (current === "contact") {
      if (detail.client.max_linked) onFocusMax();
      else onSendEmail();
      return;
    }
    if (current === "documents") {
      if (funnel.docsRequiredOk) onRequestReview();
      else onFocusMax();
      return;
    }
    if (current === "diagnostics" || current === "plan") {
      onRequestReview();
      return;
    }
    scrollStage(current);
  }

  const docItems = detail.checklist_items.filter(
    (i) => i.item_type === "document" || /илс|труд|справк|выписк|стаж/i.test(i.title),
  );
  const actionItems = detail.checklist_items.filter((i) => !docItems.includes(i));

  return (
    <div className="case-main">
      <div className="case-page-top case-funnel-head">
        <button
          type="button"
          className="ghost"
          onClick={onBack}
          title="Вернуться к списку дел в реестре"
        >
          ← К реестру
        </button>
        <div className="case-funnel-title-row">
          <h1>
            {detail.client.full_name ?? "Клиент"} · {caseCatalogLabel(detail.id)}
          </h1>
          <div className="case-funnel-badges">
            <span className="badge on">{stageLabel}</span>
            {detail.client.max_linked ? <span className="badge on">MAX</span> : <span className="badge">MAX нет</span>}
            {docCount === 0 ? <span className="badge">Нет документов</span> : <span className="badge on">Док. {docCount}</span>}
          </div>
        </div>
        <p className="case-funnel-meta">
          {slaHint(detail)} · Ответственный: {assigned}
        </p>
        <p className="warning inline">{detail.warning}</p>

        <div className="panel accent case-card--wide case-action-bar">
          <p className="case-action-bar-line">
            <strong>Текущий этап:</strong> {stageById[current]?.label}
            {" · "}
            <strong>Срок:</strong> {slaHint(detail)}
            {" · "}
            <strong>Следующее действие:</strong> {nextActionText || detail.next_action || "не задано"}
            {" · "}
            <strong>Ответственный:</strong> {assigned}
          </p>
          {!detail.expert_user_id ? (
            <p className="hint">Назначьте ответственного, чтобы зафиксировать владение делом.</p>
          ) : null}
          <div className="filters case-action-bar-fields">
            <label>
              Что сделать
              <input
                value={nextActionText}
                onChange={(e) => onNextActionText(e.target.value)}
                placeholder="Запросить трудовую книжку"
              />
            </label>
            <label>
              Срок
              <input
                type="datetime-local"
                value={nextActionAt}
                onChange={(e) => onNextActionAt(e.target.value)}
              />
            </label>
            <label>
              Исполнитель
              <select value={waitingOn} onChange={(e) => onWaitingOn(e.target.value)}>
                <option value="staff">Сотрудник</option>
                <option value="client">Клиент</option>
                <option value="archive">Архив</option>
                <option value="sfr">СФР</option>
                <option value="payment">Оплата</option>
                <option value="none">Не задано</option>
              </select>
            </label>
          </div>
          <div className="row-actions case-funnel-cta-row">
            {!detail.expert_user_id || detail.expert_user_id !== meUserId ? (
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={onTake}
                title="Назначить это дело на себя"
              >
                Назначить себя
              </button>
            ) : null}
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={onSuggestStep}
              title="DeepSeek предложит действие и черновики. В MAX не отправит"
            >
              {busy ? "DeepSeek думает…" : "Подставить шаблон"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onSaveNextAction}
              title="Сохранить следующий шаг, срок и исполнителя"
            >
              Сохранить
            </button>
            <button
              type="button"
              disabled={busy || !canAct(current)}
              onClick={runPrimaryCta}
              title={stageById[current]?.reason || "Главное действие этапа"}
            >
              {cta}
            </button>
            <details className="case-funnel-more">
              <summary className="ghost" title="Служебные ссылки">
                ⋮
              </summary>
              <div className="case-funnel-more-menu">
                {detail.client.max_linked ? (
                  <button type="button" className="linkish" onClick={onFocusMax}>
                    Написать в MAX
                  </button>
                ) : null}
                <a href={detail.channels.cabinet_url} target="_blank" rel="noreferrer">
                  Кабинет клиента
                </a>
                {detail.crm_url ? (
                  <a href={detail.crm_url} target="_blank" rel="noreferrer">
                    amoCRM
                  </a>
                ) : null}
                {detail.meeting_url ? (
                  <a href={detail.meeting_url} target="_blank" rel="noreferrer">
                    Телемост
                  </a>
                ) : null}
                <button type="button" className="linkish" disabled={busy} onClick={onCreateTelemost}>
                  Создать Телемост
                </button>
                <button type="button" className="linkish" disabled={busy} onClick={onSendEmail}>
                  Письмо: документы
                </button>
              </div>
            </details>
          </div>
          {stepHint ? (
            <div className="case-step-hint">
              <p>
                <strong>{stepHint.source === "deepseek" ? "DeepSeek" : "По этапу"}:</strong>{" "}
                {stepHint.action}
              </p>
              {stepHint.reason ? <p className="hint">{stepHint.reason}</p> : null}
              {stepMessages.length > 0 ? (
                <div className="case-step-hint-msgs">
                  {stepMessages.map((msg) => (
                    <button
                      key={`${msg.kind}-${msg.text.slice(0, 40)}`}
                      type="button"
                      className="case-chat-btn-chip case-chat-btn-chip--clickable"
                      onClick={() => applyTemplate(msg.text)}
                      title="Подставить в поле чата. Отправка в MAX — отдельно"
                    >
                      {KIND_LABEL[msg.kind]}:{" "}
                      {msg.text.length > 60 ? `${msg.text.slice(0, 60)}…` : msg.text}
                    </button>
                  ))}
                </div>
              ) : null}
              <button type="button" className="linkish" onClick={onDismissHint}>
                Скрыть подсказку
              </button>
            </div>
          ) : null}
          <p className="hint">
            Сейчас ждём: {WAITING_LABELS[waitingOn] ?? waitingOn}. Подсказка не отправляет в MAX.
          </p>
        </div>
      </div>

      <div className="case-cards case-funnel-stack">
        <div className="panel case-card--wide case-funnel-map">
          <div className="funnel-map-head">
            <h2>Воронка дела</h2>
            <label className="funnel-show-all">
              <input
                type="checkbox"
                checked={showAll}
                onChange={(e) => setShowAllPersist(e.target.checked)}
              />
              Показать все этапы
            </label>
          </div>
          <ul className="funnel-grid funnel-stepper">
            {funnel.stages.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`funnel-item funnel-item--${s.state}`}
                  title={s.reason}
                  onClick={() => scrollStage(s.id)}
                >
                  <StageMark state={s.state} />
                  <span>{s.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <StageShell
          id="funnel-contact"
          title="Контакт и доступ"
          state={stageById.contact.state}
          reason={stageById.contact.reason}
          expanded={isExpanded("contact")}
          forceShow={showAll}
          onToggle={() => scrollStage("contact")}
          accent={current === "contact"}
        >
          <p>
            MAX: {detail.client.max_linked ? "привязан" : "нет"}
            {detail.client.max_user_id ? ` · ${detail.client.max_user_id}` : ""}
            {" · "}Кабинет: {detail.client.web_linked ? "активирован" : "не активирован"}
            {" · "}Согласие на ПДн: {funnel.consentOk ? "получено / не lead" : "нужно"}
            {" · "}Канал:{" "}
            {CHANNEL_LABELS[detail.client.preferred_channel] ?? detail.client.preferred_channel}
          </p>
          <p className="hint">
            Телефон: {detail.client.phone || "не указан"}
            {detail.client.email ? ` · ${detail.client.email}` : ""}
          </p>
          <div className="row-actions">
            {detail.client.max_linked ? (
              <button
                type="button"
                className="max-action-btn max-action-btn--inline"
                disabled={!canAct("contact") && !showAll}
                onClick={onFocusMax}
                title={stageById.contact.reason}
              >
                Написать в MAX
              </button>
            ) : null}
            <a href={detail.channels.cabinet_url} target="_blank" rel="noreferrer">
              Открыть кабинет
            </a>
          </div>
          <div className="rep-block">
            <button type="button" className="linkish" onClick={() => setRepOpen((v) => !v)}>
              {repOpen ? "− Скрыть представителей" : "+ Добавить законного представителя"}
            </button>
            {repOpen || (detail.representatives ?? []).length > 0 ? (
              <>
                <p className="hint warning-inline">
                  Нужно основание полномочий (доверенность / законное представительство). Не запрашивайте
                  СНИЛС и сканы в чат.
                </p>
                <ul className="plain-list">
                  {(detail.representatives ?? []).length === 0 && <li>Нет</li>}
                  {(detail.representatives ?? []).map((rep) => (
                    <li key={rep.user_id}>
                      {rep.full_name || rep.email || rep.user_id.slice(0, 8)}{" "}
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => onRemoveRepresentative(rep.user_id)}
                      >
                        Снять
                      </button>
                    </li>
                  ))}
                </ul>
                <form className="row-actions" onSubmit={onAddRepresentative}>
                  <input
                    type="email"
                    placeholder="email представителя"
                    value={repEmail}
                    onChange={(e) => onRepEmail(e.target.value)}
                    required
                  />
                  <button type="submit" disabled={busy}>
                    Выдать доступ
                  </button>
                </form>
              </>
            ) : null}
          </div>
        </StageShell>

        <StageShell
          id="funnel-documents"
          title={`Документы · ${docCount}`}
          state={stageById.documents.state}
          reason={stageById.documents.reason}
          expanded={isExpanded("documents")}
          forceShow={showAll}
          onToggle={() => scrollStage("documents")}
          accent={current === "documents"}
        >
          <table className="case-docs-table">
            <thead>
              <tr>
                <th>Документ</th>
                <th>Состояние</th>
                <th>Источник</th>
                <th>Последнее действие</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Выписка ИЛС</td>
                <td>{funnel.hasIls ? "есть" : "нет"}</td>
                <td>кабинет / чек-лист</td>
                <td>
                  <button
                    type="button"
                    className="linkish"
                    disabled={!canAct("documents") && current !== "documents" && !showAll}
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Подставить шаблон «Запросить ИЛС» в чат? Отправка в MAX — отдельно.",
                        )
                      )
                        return;
                      applyTemplate(DOC_REQUEST_ILS);
                    }}
                    title="Шаблон в composer, без автоотправки"
                  >
                    Отправить шаблон
                  </button>
                </td>
              </tr>
              <tr>
                <td>Трудовая / сведения о стаже</td>
                <td>{funnel.hasLabor ? "есть" : "нет"}</td>
                <td>кабинет / чек-лист</td>
                <td>
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Подставить шаблон «Запросить трудовую» в чат? Отправка в MAX — отдельно.",
                        )
                      )
                        return;
                      applyTemplate(DOC_REQUEST_LABOR);
                    }}
                  >
                    Отправить шаблон
                  </button>
                </td>
              </tr>
              {detail.documents.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <button type="button" className="linkish" onClick={() => onOpenSigned(doc.id)}>
                      {doc.storage_path.split("/").pop()}
                    </button>
                  </td>
                  <td>загружен</td>
                  <td>{docSourceLabel(doc)}</td>
                  <td>
                    {doc.created_at
                      ? new Date(doc.created_at).toLocaleString("ru-RU", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {docItems.length > 0 ? (
            <ul className="plain-list case-doc-checklist">
              {docItems.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="linkish"
                    disabled={!caps.can_edit_checklist}
                    onClick={() => onToggleChecklist(item.id, item.status)}
                  >
                    [{labelChecklistStatus(item.status)}] {item.title}
                  </button>
                  <span className="hint"> · {labelChecklistOwner(item.owner)}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {caps.can_edit_checklist ? (
            <form className="inline-form" onSubmit={onAddChecklist}>
              <input
                value={checklistTitle}
                onChange={(e) => onChecklistTitle(e.target.value)}
                placeholder="Пункт по документу"
                required
              />
              <button type="submit">Добавить в чек-лист</button>
            </form>
          ) : null}
          <div className="row-actions">
            <a href={detail.channels.cabinet_url} target="_blank" rel="noreferrer">
              Открыть защищённый кабинет
            </a>
            <button
              type="button"
              disabled={busy || !funnel.docsRequiredOk || (!canAct("documents") && !canAct("diagnostics"))}
              onClick={onRequestReview}
              title={
                funnel.docsRequiredOk
                  ? "Запустить проверку"
                  : `Для диагностики не хватает: ${funnel.missingDocs.join(", ")}`
              }
            >
              Проверить документы
            </button>
          </div>
        </StageShell>

        {caps.can_view_ocr ? (
          <StageShell
            id="funnel-diagnostics"
            title="Диагностика"
            state={stageById.diagnostics.state}
            reason={stageById.diagnostics.reason}
            expanded={isExpanded("diagnostics")}
            forceShow={showAll}
            onToggle={() => scrollStage("diagnostics")}
            accent={current === "diagnostics"}
          >
            <p className="hint">
              Статус: {stageLabel}. ИЛС — {funnel.hasIls ? "есть" : "нет"} · трудовая —{" "}
              {funnel.hasLabor ? "есть" : "нет"}. OCR: {(detail.ocr_texts ?? []).length}
            </p>
            <div className="row-actions">
              <button
                type="button"
                disabled={busy || !funnel.docsRequiredOk || !canAct("diagnostics")}
                onClick={onRequestReview}
                title={
                  funnel.docsRequiredOk
                    ? "Запустить проверку"
                    : `Для диагностики не хватает: ${funnel.missingDocs.join(", ")}`
                }
              >
                Проверить документы
              </button>
            </div>
            <h3 className="case-subhead">Замечания / расхождения</h3>
            <ul className="plain-list">
              {(detail.findings ?? []).length === 0 && (
                <li className="hint">Пока нет — запустите проверку</li>
              )}
              {(detail.findings ?? []).map((f, idx) => (
                <li key={`${f.type}-${idx}`}>
                  <strong>{f.type}</strong> {f.detail}
                </li>
              ))}
            </ul>
            <h3 className="case-subhead">Помощь в анализе</h3>
            <p className="hint">Сформировано ИИ, требует проверки</p>
            {detail.analysis_notes ? (
              <pre className="draft">{detail.analysis_notes}</pre>
            ) : (
              <p className="hint">Появится после проверки.</p>
            )}
          </StageShell>
        ) : null}

        <StageShell
          id="funnel-plan"
          title="План действий и проект обращения"
          state={stageById.plan.state}
          reason={stageById.plan.reason}
          expanded={isExpanded("plan")}
          forceShow={showAll}
          onToggle={() => scrollStage("plan")}
          accent={current === "plan"}
        >
          <p className="hint">
            Черновик требует проверки специалистом. Не является решением СФР. Клиент подаёт сам.
          </p>
          {detail.draft ? (
            <pre className="draft">
              {detail.draft.title}
              {"\n\n"}
              {detail.draft.body}
            </pre>
          ) : (
            <p className="hint">Проекта пока нет — сначала диагностика.</p>
          )}
          <div className="row-actions">
            <button
              type="button"
              disabled={busy || !caps.can_view_ocr || !canAct("plan")}
              onClick={onRequestReview}
              title={stageById.plan.reason}
            >
              Сформировать / обновить проект
            </button>
            {detail.draft?.body ? (
              <button
                type="button"
                className="ghost"
                disabled={!canAct("plan") && !showAll}
                onClick={() => applyTemplate(PLAN_READY_CHAT)}
              >
                Подставить сообщение клиенту
              </button>
            ) : null}
          </div>
        </StageShell>

        {caps.can_manage_orders ? (
          <StageShell
            id="funnel-payment"
            title="Услуга и оплата"
            state={stageById.payment.state}
            reason={stageById.payment.reason}
            expanded={isExpanded("payment")}
            forceShow={showAll}
            onToggle={() => scrollStage("payment")}
            accent={current === "payment"}
          >
            {(detail.orders ?? []).length > 0 ? (
              <ul className="plain-list">
                {(detail.orders ?? []).map((o) => (
                  <li key={o.id}>
                    {labelPackage(o.package_code)} · {o.amount_rub} ₽ · {o.status}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">Услуга ещё не согласована / счёт не создан.</p>
            )}
            <div className="row-actions">
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={onRecordServiceConsent}
                title="Зафиксировать согласие клиента на услугу (audit)"
              >
                Зафиксировать согласие клиента
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => applyTemplate(SERVICE_DESCRIPTION_CHAT)}
              >
                Отправить описание услуги в чат
              </button>
            </div>
            {!funnel.serviceConsentOk ? (
              <p className="hint">Создать счёт можно после фиксации согласия (или если статус не lead).</p>
            ) : null}
            <form className="inline-form" onSubmit={onCreateOrder}>
              <select
                value={orderCode}
                onChange={(e) => onOrderCode(e.target.value as typeof orderCode)}
                disabled={!funnel.serviceConsentOk}
              >
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
                onChange={(e) => onOrderAmount(e.target.value)}
                required
                disabled={!funnel.serviceConsentOk}
              />
              <button
                type="submit"
                disabled={!funnel.serviceConsentOk || !canAct("payment")}
                title={
                  funnel.serviceConsentOk
                    ? "Создать счёт"
                    : "Сначала зафиксируйте согласие клиента на услугу"
                }
              >
                Создать счёт
              </button>
            </form>
            <p className="hint">Сумма по услуге / договору. Не путать с решением СФР.</p>
          </StageShell>
        ) : null}

        {caps.can_confirm_result ? (
          <StageShell
            id="funnel-result"
            title="Ответ СФР и итог по делу"
            state={stageById.result.state}
            reason={stageById.result.reason}
            expanded={isExpanded("result")}
            forceShow={showAll}
            onToggle={() => scrollStage("result")}
            accent={current === "result"}
          >
            <label className="funnel-show-all">
              <input
                type="checkbox"
                checked={sfrReceived}
                onChange={(e) => onSfrReceived(e.target.checked)}
              />
              Ответ СФР получен
            </label>
            {sfrReceived ? (
              <form className="stack-form" onSubmit={onConfirmResult}>
                <label>
                  Прежний размер, ₽ (из решения СФР)
                  <input value={beforeRub} onChange={(e) => onBeforeRub(e.target.value)} required />
                </label>
                <label>
                  Новый размер, ₽ (из решения СФР)
                  <input value={afterRub} onChange={(e) => onAfterRub(e.target.value)} required />
                </label>
                <label>
                  Единовременная выплата, ₽
                  <input
                    value={lumpRub}
                    onChange={(e) => onLumpRub(e.target.value)}
                    placeholder="Не указано — только по документу СФР"
                  />
                </label>
                <button type="submit" disabled={!canAct("result") && !showAll}>
                  Зафиксировать ответ СФР
                </button>
              </form>
            ) : (
              <p className="hint">Включите переключатель, когда решение СФР получено.</p>
            )}
            <p className="hint">Только факты из решения СФР, не цена услуги сервиса.</p>
          </StageShell>
        ) : null}

        {caps.can_knowledge_feedback ? (
          <StageShell
            id="funnel-feedback"
            title="Обезличенный вывод в базу знаний"
            state={stageById.feedback.state}
            reason={stageById.feedback.reason}
            expanded={isExpanded("feedback")}
            forceShow={showAll}
            onToggle={() => scrollStage("feedback")}
            accent={current === "feedback"}
          >
            <form className="stack-form" onSubmit={onSendFeedback}>
              <textarea
                rows={2}
                value={feedbackText}
                onChange={(e) => onFeedbackText(e.target.value)}
                placeholder="Что помогло (без ФИО, СНИЛС, номеров дел)"
                required
              />
              <div className="inline-form">
                <select value={feedbackQuality} onChange={(e) => onFeedbackQuality(e.target.value)}>
                  <option value="draft">{labelFeedbackQuality("draft")}</option>
                  <option value="verified">{labelFeedbackQuality("verified")}</option>
                  <option value="template">{labelFeedbackQuality("template")}</option>
                  <option value="rejected">{labelFeedbackQuality("rejected")}</option>
                </select>
                <button type="submit">Сохранить</button>
              </div>
            </form>
          </StageShell>
        ) : null}

        <details className="panel service-details case-card--wide">
          <summary>Служебное · журнал</summary>
          <p className="hint">ID: {detail.id}</p>
          <p>
            pipeline={detail.pipeline_status} · b2c={detail.b2c_status}
          </p>
          {actionItems.length > 0 ? (
            <>
              <h3 className="case-subhead">Чек-лист (действия)</h3>
              <ul className="plain-list">
                {actionItems.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="linkish"
                      disabled={!caps.can_edit_checklist}
                      onClick={() => onToggleChecklist(item.id, item.status)}
                    >
                      [{labelChecklistStatus(item.status)}] {item.title}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {caps.can_edit_pipeline ? (
            <div className="inline-form">
              <select value={pipelineStatus} onChange={(e) => onPipelineStatus(e.target.value)}>
                {pipelineStageOptions().map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <button type="button" onClick={onSavePipeline}>
                Сохранить этап пайплайна
              </button>
            </div>
          ) : null}
          {detail.crm_url ? (
            <p>
              amoCRM:{" "}
              <a href={detail.crm_url} target="_blank" rel="noreferrer">
                открыть
              </a>
            </p>
          ) : null}
          <h3 className="case-subhead">Последние события</h3>
          <ul className="plain-list case-audit-list">
            {auditPreview.map((row, idx) => (
              <li key={`${row.at}-${idx}`}>
                {row.action} · {new Date(row.at).toLocaleString("ru-RU")}
              </li>
            ))}
          </ul>
          {auditRest.length > 0 ? (
            <details>
              <summary>Весь журнал ({detail.audit.length})</summary>
              <ul className="plain-list case-audit-list">
                {auditRest.map((row, idx) => (
                  <li key={`${row.at}-r-${idx}`}>
                    {row.action} · {new Date(row.at).toLocaleString("ru-RU")}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </details>
      </div>
    </div>
  );
}

export type { FunnelStageId };
