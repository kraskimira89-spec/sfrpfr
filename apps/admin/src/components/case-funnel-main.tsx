"use client";

import {
  DOC_REQUEST_ILS,
  DOC_REQUEST_LABOR,
  PLAN_READY_CHAT,
  SERVICE_DESCRIPTION_CHAT,
  deriveFunnel,
  primaryCtaLabel,
  type FunnelStageId,
  type FunnelStageState,
} from "@/lib/case-funnel";
import {
  chatAwaitsStaff,
  situationBadges,
  slaTone,
  slaToneLabel,
} from "@/lib/case-indicators";
import {
  humanCaseStage,
  labelChecklistOwner,
  labelChecklistStatus,
  labelFeedbackQuality,
  labelPackage,
  pipelineStageOptions,
} from "@/lib/ui-labels";
import { caseCatalogLabel } from "@/components/cases-registry";
import { DocumentsTable } from "@/components/documents-table";
import { DiagnosisDeliveryPanel } from "@/components/diagnosis-delivery-panel";
import { LOSS_REASON_VALUES } from "@/lib/sales-board";
import { FormEvent, useMemo, useState, type ReactNode } from "react";

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
  is_test?: boolean;
  silent_days?: number;
  archive_prep_status?: string | null;
  archive_tariff?: string | null;
  archive_successor?: string | null;
  archive_target?: string | null;
  archive_followup_at?: string | null;
  loss_reason?: string | null;
  closed_at?: string | null;
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
    max_ops_bot_url?: string | null;
    max_reply_url?: string | null;
  };
  representatives?: {
    user_id: string;
    email?: string | null;
    full_name?: string | null;
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
  cabinet_howto: "Как передать документы",
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
}: {
  id: string;
  title: string;
  state: FunnelStageState;
  reason: string;
  expanded: boolean;
  forceShow: boolean;
  onToggle: () => void;
  children: ReactNode;
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
    <div id={id} className={`panel funnel-stage funnel-stage--${state}`}>
      <button type="button" className="funnel-stage-toggle" onClick={onToggle} title={reason}>
        <StageMark state={state} />
        <strong>{title}</strong>
        {!expanded && forceShow ? <span className="hint">просмотр</span> : null}
      </button>
      <div className="funnel-stage-body">{children}</div>
    </div>
  );
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
  chatMessages = [],
  onBack,
  onPrevCase,
  onNextCase,
  canPrevCase = false,
  canNextCase = false,
  onNextActionText,
  onNextActionAt,
  onWaitingOn,
  onSaveNextAction,
  onSaveArchivePrep,
  onCloseCase,
  onSuggestStep,
  onApplyChatMessage,
  onDismissHint,
  onTake,
  onFocusMax,
  onOpenFinance,
  onRequestReview,
  onCreateTelemost,
  onSendEmail,
  onOpenTrackerModal,
  onOpenSigned,
  onUploadDiagnosisReport,
  onPublishDiagnosis,
  staffToken,
  apiBase,
  onDeliveryNotice,
  onDeliveryRefresh,
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
  onSendPayLink,
  onCopyPayLink,
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
  /** Сообщения чата — для бейджа «Нужен ответ». */
  chatMessages?: Array<{ author_kind: string }>;
  onBack: () => void;
  onPrevCase?: () => void;
  onNextCase?: () => void;
  canPrevCase?: boolean;
  canNextCase?: boolean;
  onNextActionText: (v: string) => void;
  onNextActionAt: (v: string) => void;
  onWaitingOn: (v: string) => void;
  onSaveNextAction: () => void;
  onSaveArchivePrep: (payload: {
    archive_prep_status: string | null;
    archive_tariff: string | null;
    archive_successor: string | null;
    archive_target: string | null;
    archive_followup_at: string | null;
  }) => void;
  onCloseCase?: (payload: { outcome: "success" | "lost"; loss_reason?: string }) => void;
  onSuggestStep: () => void;
  onApplyChatMessage: (text: string, opts?: { confirmAssign?: boolean }) => void;
  onDismissHint: () => void;
  onTake: () => void;
  onFocusMax: () => void;
  /** Переход на вкладку Финансы по этому делу (счета, не этап pipeline). */
  onOpenFinance?: () => void;
  onRequestReview: () => void;
  onCreateTelemost: () => void;
  onSendEmail: () => void;
  onOpenTrackerModal: () => void;
  onOpenSigned: (docId: string) => void;
  onUploadDiagnosisReport: (file: File) => void;
  onPublishDiagnosis: (documentId: string) => void;
  staffToken?: string | null;
  apiBase?: string;
  onDeliveryNotice?: (msg: string) => void;
  onDeliveryRefresh?: () => void;
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
  onSendPayLink?: (orderId: string) => void;
  onCopyPayLink?: (orderId: string) => void;
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

  const indicatorInput = useMemo(
    () => ({
      waiting_on: waitingOn || detail.waiting_on,
      is_test: detail.is_test,
      pipeline_status: detail.pipeline_status,
      b2c_status: detail.b2c_status,
      expert_user_id: detail.expert_user_id,
      max_linked: detail.client.max_linked,
      web_linked: detail.client.web_linked,
      silent_days: detail.silent_days,
      consent_accepted: detail.consent_accepted,
      chat_awaits_staff: chatAwaitsStaff(chatMessages) || waitingOn === "staff",
    }),
    [detail, waitingOn, chatMessages],
  );
  const sla = slaTone(indicatorInput);
  const sitBadges = useMemo(
    () => situationBadges(indicatorInput, { meUserId }),
    [indicatorInput, meUserId],
  );

  const [showAll, setShowAll] = useState(() => {
    try {
      return typeof window !== "undefined" && localStorage.getItem(SHOW_ALL_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [manualOpen, setManualOpen] = useState<FunnelStageId | null>(null);
  const [focusKey, setFocusKey] = useState(`${detail.id}:${current}`);
  const [repOpen, setRepOpen] = useState(false);

  const nextFocusKey = `${detail.id}:${current}`;
  if (focusKey !== nextFocusKey) {
    setFocusKey(nextFocusKey);
    setManualOpen(null);
  }

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
        <div className="case-nav-bar" role="navigation" aria-label="Навигация по делам">
          <button
            type="button"
            className="ghost"
            onClick={onBack}
            title="Вернуться к списку дел в реестре"
          >
            ← К реестру
          </button>
          <button
            type="button"
            className="ghost"
            disabled={!canPrevCase || busy}
            onClick={() => onPrevCase?.()}
            title="Предыдущее дело в текущем списке реестра"
          >
            ← Предыдущее дело
          </button>
          <button
            type="button"
            className="ghost"
            disabled={!canNextCase || busy}
            onClick={() => onNextCase?.()}
            title="Следующее дело в текущем списке реестра"
          >
            Следующее дело →
          </button>
        </div>
        <div className="case-funnel-title-row">
          <h1>
            {detail.client.full_name ?? "Клиент"} · {caseCatalogLabel(detail.id)}
          </h1>
          <div className="case-funnel-badges">
            <span
              className={`prio-dot prio-dot--${sla}`}
              title={`Срочность: ${slaToneLabel(sla)}`}
              aria-label={slaToneLabel(sla)}
            />
            <span className={`badge badge--${sla === "calm" ? "docs" : sla === "muted" ? "test" : "reply"}`} title="Срочность SLA (не этап воронки)">
              {slaToneLabel(sla)}
            </span>
            {sitBadges.map((b) => (
              <span key={b.id} className={`badge badge--${b.kind}`} title={b.title}>
                {b.label}
              </span>
            ))}
            <span className="badge on" title="Текущий этап воронки — здесь идёт работа">
              Этап: {stageById[current]?.label ?? stageLabel}
            </span>
            <span
              className="badge"
              title="Статус в реестре дел (может отличаться от этапа воронки, пока не обновлён вручную)"
            >
              В реестре: {stageLabel}
            </span>
            {docCount === 0 ? (
              <span className="badge" title="В деле пока нет загруженных файлов">
                Нет документов
              </span>
            ) : (
              <span className="badge on" title="Число загруженных файлов в деле">
                Док. {docCount}
              </span>
            )}
          </div>
        </div>
        <p className="case-funnel-meta">
          Ответственный: {assigned}
          {stageById[current]?.reason ? ` · ${stageById[current].reason}` : ""}
        </p>
        {detail.warning ? (
          <p className="warning inline" title="Постоянное предупреждение сервиса">
            {detail.warning}
          </p>
        ) : null}

        <div className="panel accent case-card--wide case-action-bar">
          <p className="case-action-bar-line">
            <strong>Сейчас:</strong> {stageById[current]?.label}
            {stageById[current]?.reason ? ` (${stageById[current].reason})` : ""}
            {" · "}
            <strong>Следующее действие:</strong> {nextActionText || detail.next_action || "не задано"}
            {" · "}
            <strong>Ответственный:</strong> {assigned}
          </p>
          {!detail.expert_user_id ? (
            <p className="hint">Назначьте ответственного, чтобы зафиксировать владение делом.</p>
          ) : null}
          <div className="filters case-action-bar-fields">
            <label title="Что сотрудник или клиент должен сделать дальше">
              Что сделать
              <input
                value={nextActionText}
                onChange={(e) => onNextActionText(e.target.value)}
                placeholder="Запросить трудовую книжку"
                title="Кратко: следующий шаг по делу"
              />
            </label>
            <label title="Когда проверить выполнение по этому шагу">
              Срок
              <input
                type="datetime-local"
                value={nextActionAt}
                onChange={(e) => onNextActionAt(e.target.value)}
                title="Дедлайн следующего действия"
              />
            </label>
            <label title="Кто должен действовать: сотрудник, клиент, СФР и т.д.">
              Исполнитель
              <select
                value={waitingOn}
                onChange={(e) => onWaitingOn(e.target.value)}
                title="От кого ждём следующий шаг"
              >
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
                title="Назначить это дело на себя: вы станете ответственным сотрудником"
                aria-label="Назначить дело на себя"
              >
                Назначить себя
              </button>
            ) : null}
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={onSuggestStep}
              title="DeepSeek предложит следующий шаг и черновики сообщений. В MAX ничего не отправит — только подставит текст"
              aria-label="Подставить шаблон через DeepSeek"
            >
              {busy ? "DeepSeek думает…" : "Подставить шаблон"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onSaveNextAction}
              title="Сохранить поля «Что сделать», «Срок» и «Исполнитель» в карточке дела"
              aria-label="Сохранить следующий шаг"
            >
              Сохранить
            </button>
            <button
              type="button"
              disabled={busy || !canAct(current)}
              onClick={runPrimaryCta}
              title={
                stageById[current]?.reason
                  ? `${cta}: ${stageById[current].reason}`
                  : `Главное действие текущего этапа «${stageById[current]?.label ?? ""}»`
              }
              aria-label={cta}
            >
              {cta}
            </button>
            <details className="case-funnel-more">
              <summary
                className="ghost"
                title="Дополнительно: MAX, кабинет клиента, amoCRM, Телемост, Tracker, письмо"
                aria-label="Ещё действия"
              >
                ⋮
              </summary>
              <div className="case-funnel-more-menu">
                {detail.client.max_linked ? (
                  <button
                    type="button"
                    className="linkish"
                    onClick={onFocusMax}
                    title="Перейти к полю ответа в чате MAX справа"
                  >
                    Написать в MAX
                  </button>
                ) : null}
                <a
                  href={detail.channels.cabinet_url}
                  target="_blank"
                  rel="noreferrer"
                  title="Открыть личный кабинет клиента в новой вкладке"
                >
                  Кабинет клиента
                </a>
                {detail.crm_url ? (
                  <a
                    href={detail.crm_url}
                    target="_blank"
                    rel="noreferrer"
                    title="Открыть карточку лида в amoCRM"
                  >
                    amoCRM
                  </a>
                ) : null}
                {detail.meeting_url ? (
                  <a
                    href={detail.meeting_url}
                    target="_blank"
                    rel="noreferrer"
                    title="Открыть ссылку на встречу Телемост"
                  >
                    Телемост
                  </a>
                ) : null}
                {detail.tracker_issue_url && detail.tracker_last_issue_key ? (
                  <a
                    href={detail.tracker_issue_url}
                    target="_blank"
                    rel="noreferrer"
                    title="Открыть связанную задачу в Яндекс Трекере"
                  >
                    Трекер {detail.tracker_last_issue_key}
                  </a>
                ) : null}
                <button
                  type="button"
                  className="linkish"
                  disabled={busy}
                  onClick={onCreateTelemost}
                  title="Создать новую встречу Яндекс Телемост и сохранить ссылку в деле"
                >
                  Создать Телемост
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busy}
                  onClick={onOpenTrackerModal}
                  title="Создать обезличенную задачу качества в Трекере (без ПДн клиента)"
                >
                  Создать задачу в Tracker
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={busy}
                  onClick={onSendEmail}
                  title="Отправить клиенту письмо с запросом документов на его e-mail"
                >
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

      <ArchivePrepBlock detail={detail} busy={busy} onSave={onSaveArchivePrep} />
      {onCloseCase ? (
        <CloseCaseBlock
          detail={detail}
          busy={busy}
          onClose={onCloseCase}
        />
      ) : null}

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
            </tbody>
          </table>
          <DocumentsTable
            documents={detail.documents}
            onOpen={onOpenSigned}
            busy={busy}
          />
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
            <h3 className="case-subhead">PDF результата клиенту</h3>
            <p className="hint">
              Канон: «Диагностика сведений о стаже…». Шаблон → PDF → загрузка сюда (
              <code>diagnosis_report</code>). Без PDF в кабинете не считать выданным.
            </p>
            {detail.documents.filter((d) =>
              `${d.doc_type || ""} ${d.storage_path || ""}`.toLowerCase().includes("diagnosis"),
            ).length > 0 ? (
              <ul className="plain-list">
                {detail.documents
                  .filter((d) =>
                    `${d.doc_type || ""} ${d.storage_path || ""}`
                      .toLowerCase()
                      .includes("diagnosis"),
                  )
                  .map((doc) => (
                    <li key={doc.id}>
                      <button type="button" className="linkish" onClick={() => onOpenSigned(doc.id)}>
                        {doc.storage_path.split("/").pop()}
                      </button>
                      <span className="hint"> · Результат диагностики</span>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="hint">PDF ещё не загружен.</p>
            )}
            <div className="row-actions">
              <label className="secondary" style={{ cursor: busy ? "wait" : "pointer" }}>
                Загрузить PDF результата
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  hidden
                  disabled={busy || !caps.can_view_ocr}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) onUploadDiagnosisReport(file);
                  }}
                />
              </label>
              {detail.documents
                .filter((d) =>
                  `${d.doc_type || ""} ${d.storage_path || ""}`
                    .toLowerCase()
                    .includes("diagnosis"),
                )
                .slice(0, 1)
                .map((doc) => (
                  <button
                    key={`pub-${doc.id}`}
                    type="button"
                    disabled={busy || !caps.can_view_ocr}
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Опубликовать PDF и создать черновики уведомлений (e-mail/MAX)? Отправка — только после подтверждения.",
                        )
                      )
                        return;
                      onPublishDiagnosis(doc.id);
                    }}
                  >
                    Опубликовать → черновики уведомлений
                  </button>
                ))}
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={() => {
                  if (
                    !window.confirm(
                      "Подставить шаблон «Диагностика готова» в чат? Отправка в MAX — отдельно.",
                    )
                  )
                    return;
                  applyTemplate(PLAN_READY_CHAT);
                }}
              >
                Шаблон MAX: результат готов
              </button>
            </div>
            <p className="hint">
              ТЗ-28: PDF не вложением. Система готовит draft → сотрудник подтверждает отправку.
            </p>
            {staffToken && apiBase ? (
              <DiagnosisDeliveryPanel
                caseId={detail.id}
                token={staffToken}
                apiBase={apiBase}
                clientEmail={detail.client.email ?? null}
                busy={busy}
                onNotice={onDeliveryNotice ?? (() => {})}
                onRefresh={onDeliveryRefresh ?? (() => {})}
              />
            ) : null}
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
          >
            {(detail.orders ?? []).length > 0 ? (
              <ul className="plain-list case-orders-list">
                {(detail.orders ?? []).map((o) => (
                  <li key={o.id} className="case-order-card">
                    <p>
                      <strong>
                        {o.invoice_number || labelPackage(o.package_code)} · {o.amount_rub} ₽
                      </strong>
                      {" · "}
                      {o.finance_status || o.status}
                      {o.sent_channel ? ` · отправлено: ${o.sent_channel}` : ""}
                    </p>
                    {o.pay_url ? (
                      <p className="hint">
                        <a href={o.pay_url} target="_blank" rel="noreferrer">
                          Ссылка на оплату
                        </a>
                      </p>
                    ) : (
                      <p className="hint">Ссылка ещё не выставлена — нажмите «Ссылка» или «В MAX».</p>
                    )}
                    {o.qr_url && o.status !== "paid" ? (
                      <img
                        className="pay-qr"
                        src={o.qr_url}
                        alt="QR на оплату"
                        width={140}
                        height={140}
                      />
                    ) : null}
                    <div className="row-actions">
                      {onCopyPayLink ? (
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy}
                          onClick={() => onCopyPayLink(o.id)}
                        >
                          Ссылка
                        </button>
                      ) : null}
                      {onSendPayLink && detail.client.max_linked ? (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => onSendPayLink(o.id)}
                          title="Отправить счёт, ссылку и QR клиенту в MAX"
                        >
                          Отправить в MAX
                        </button>
                      ) : null}
                      {!detail.client.max_linked ? (
                        <span className="hint">MAX не привязан — только ссылка/QR здесь</span>
                      ) : null}
                    </div>
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
            <p className="hint">
              Просрочки, «оплачено сегодня», возвраты — на вкладке Финансы, не как этап сделки в реестре.
              {onOpenFinance ? (
                <>
                  {" "}
                  <button type="button" className="linkish" onClick={onOpenFinance}>
                    Открыть Финансы по делу
                  </button>
                </>
              ) : null}
            </p>
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
          {detail.tracker_issues && detail.tracker_issues.length > 0 ? (
            <>
              <h3 className="case-subhead">Внутренние задачи Tracker</h3>
              <ul className="plain-list">
                {detail.tracker_issues.map((ti) => (
                  <li key={ti.id}>
                    {ti.tracker_issue_url ? (
                      <a href={ti.tracker_issue_url} target="_blank" rel="noreferrer">
                        {ti.tracker_issue_key}
                      </a>
                    ) : (
                      ti.tracker_issue_key
                    )}{" "}
                    · {ti.issue_type}
                    {ti.is_open === false ? " · закрыта" : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
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

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function CloseCaseBlock({
  detail,
  busy,
  onClose,
}: {
  detail: Detail;
  busy: boolean;
  onClose: (payload: { outcome: "success" | "lost"; loss_reason?: string }) => void;
}) {
  const [outcome, setOutcome] = useState<"success" | "lost">("success");
  const [reason, setReason] = useState(detail.loss_reason || "");
  const alreadyClosed = detail.b2c_status === "closed";

  return (
    <div className="panel case-card--wide" style={{ marginTop: "0.75rem" }}>
      <h2 className="case-subhead">Закрытие сделки</h2>
      <p className="hint">
        Вместо воронки amo: закрытие и причина отказа хранятся в кабинете. Оплаты — вкладка Финансы.
      </p>
      {alreadyClosed ? (
        <p>
          Уже закрыто
          {detail.loss_reason ? ` · отказ: ${detail.loss_reason}` : " · успешно"}
          {detail.closed_at
            ? ` · ${new Date(detail.closed_at).toLocaleString("ru-RU")}`
            : ""}
        </p>
      ) : (
        <div className="filters case-action-bar-fields">
          <label>
            Итог
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as "success" | "lost")}
            >
              <option value="success">Успешно закрыто</option>
              <option value="lost">Отказ</option>
            </select>
          </label>
          {outcome === "lost" ? (
            <label>
              Причина отказа
              <select value={reason} onChange={(e) => setReason(e.target.value)}>
                <option value="">— выберите —</option>
                {LOSS_REASON_VALUES.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            disabled={busy || (outcome === "lost" && !reason)}
            onClick={() =>
              onClose({
                outcome,
                loss_reason: outcome === "lost" ? reason : undefined,
              })
            }
          >
            Закрыть дело
          </button>
        </div>
      )}
    </div>
  );
}

function ArchivePrepBlock({
  detail,
  busy,
  onSave,
}: {
  detail: Detail;
  busy: boolean;
  onSave: (payload: {
    archive_prep_status: string | null;
    archive_tariff: string | null;
    archive_successor: string | null;
    archive_target: string | null;
    archive_followup_at: string | null;
  }) => void;
}) {
  const [status, setStatus] = useState(detail.archive_prep_status || "");
  const [tariff, setTariff] = useState(detail.archive_tariff || "");
  const [successor, setSuccessor] = useState(detail.archive_successor || "");
  const [target, setTarget] = useState(detail.archive_target || "");
  const [followup, setFollowup] = useState(toLocalInput(detail.archive_followup_at));

  return (
    <div className="panel case-card--wide" style={{ marginTop: "0.75rem" }}>
      <h2 className="case-subhead">Архивный комплект</h2>
      <p className="hint">
        Без ПДн и сканов. Тариф: 5000 (подготовка) / 8000 (до подачи). Исполнитель «Архив» —
        в блоке следующего шага.
      </p>
      <div className="filters case-action-bar-fields">
        <label>
          Статус
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">—</option>
            <option value="diagnosis_ready">Диагностика готова</option>
            <option value="period_collected">Сведения о периоде</option>
            <option value="route_agreed">Маршрут согласован</option>
            <option value="request_drafted">Проект запроса</option>
            <option value="client_review">Проверка клиентом</option>
            <option value="pack_issued">Комплект выдан</option>
            <option value="awaiting_archive">Ожидаем ответ архива</option>
            <option value="archive_reply">Ответ получен</option>
            <option value="next_step">Нужен следующий шаг</option>
            <option value="closed">Закрыто</option>
          </select>
        </label>
        <label>
          Тариф
          <select value={tariff} onChange={(e) => setTariff(e.target.value)}>
            <option value="">—</option>
            <option value="5000">5 000</option>
            <option value="8000">8 000</option>
          </select>
        </label>
        <label>
          Правопреемник
          <select value={successor} onChange={(e) => setSuccessor(e.target.value)}>
            <option value="">—</option>
            <option value="известен">известен</option>
            <option value="неизвестен">неизвестен</option>
            <option value="проверить">проверить</option>
          </select>
        </label>
        <label>
          Адресат
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">—</option>
            <option value="предполагаемый">предполагаемый</option>
            <option value="подтверждённый">подтверждённый</option>
          </select>
        </label>
        <label>
          Контрольная дата
          <input
            type="datetime-local"
            value={followup}
            onChange={(e) => setFollowup(e.target.value)}
          />
        </label>
      </div>
      <button
        type="button"
        disabled={busy}
        onClick={() =>
          onSave({
            archive_prep_status: status || null,
            archive_tariff: tariff || null,
            archive_successor: successor || null,
            archive_target: target || null,
            archive_followup_at: followup ? new Date(followup).toISOString() : null,
          })
        }
      >
        Сохранить архивный блок
      </button>
    </div>
  );
}

export type { FunnelStageId };
