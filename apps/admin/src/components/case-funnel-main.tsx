"use client";

import {
  DOC_REQUEST_ILS,
  DOC_REQUEST_LABOR,
  PLAN_READY_CHAT,
  SERVICE_DESCRIPTION_CHAT,
  primaryCtaLabel,
  type FunnelStageId,
} from "@/lib/case-funnel";
import { deriveFunnel } from "@/lib/case-funnel-facts";
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
  labelOrderStatus,
  labelPackage,
  pipelineStageOptions,
} from "@/lib/ui-labels";
import { caseCatalogLabel } from "@/components/cases-registry";
import { displayClientFio } from "@/lib/client-display-name";
import { DocumentsTable } from "@/components/documents-table";
import { CaseWorkRoute, type WorkRoute } from "@/components/case-work-route";
import { StageNavContext, StageShell, type StageNav } from "@/components/case-stage-shell";
import {
  initialAccordion,
  openStageOf,
  toggleAccordion,
  type StageAccordion,
} from "@/lib/case-funnel-accordion";
import { DiagnosisDeliveryPanel } from "@/components/diagnosis-delivery-panel";
import { LOSS_REASON_VALUES } from "@/lib/sales-board";
import { DocumentCheckPanel } from "@/components/document-check-panel";
import { StepNo } from "@/components/step-number";
import { groupCabinetDocumentsByChecksum } from "@/lib/dedupe-cabinet-documents";
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
    downloadable?: boolean | null;
    ingest_status?: string | null;
    antivirus_status?: string | null;
    mime_verified?: string | null;
    ingest_review_required?: boolean | null;
    progress_message?: string | null;
    has_local_file?: boolean | null;
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
  work_route?: WorkRoute | null;
  document_check?: {
    job_id?: string;
    status?: string;
    status_label?: string;
    stale?: boolean;
    current_stage?: string | null;
    last_error?: string | null;
    result?: {
      documents_checked?: number;
      originals_available?: number;
      text_extracted?: number;
      needs_recognition?: number;
      needs_manual_review?: number;
      types_found?: string[];
      exact_duplicate_groups?: number;
      missing_for_task?: string[];
      missing_explanations?: string[];
      next_action?: string;
      ocr_allowed?: boolean;
      legal_analysis_ran?: boolean;
      status?: string;
      honest_brief?: {
        current?: boolean;
        stale_reason?: string;
        has_justified_discrepancy?: boolean;
        offer_diag_allowed?: boolean;
        offer_amount_rub?: number;
        headline?: string;
        next_step?: string;
        items?: {
          text?: string;
          evidence?: string;
          evidence_label?: string;
          basis?: string;
        }[];
        disclaimer?: string;
      } | null;
      diag_offer?: {
        allowed?: boolean;
        amount_rub?: number;
        label?: string;
        note?: string;
      } | null;
    } | null;
  } | null;
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

function NotWiredNote({ label }: { label: string }) {
  return (
    <p className="hint">
      {label}: функция ещё не подключена. Карточка для навигации; действий и API-мутаций здесь нет.
    </p>
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
  onPolishBriefDraft,
  onRecordFactsReview,
  onDeleteDocuments,
  onDeleteAppealDraft,
  onDismissHint,
  onTake,
  onFocusMax,
  onOpenFinance,
  onRequestReview,
  onRequestPipeline,
  onCreateTelemost,
  onSendEmail,
  onOpenTrackerModal,
  onOpenSigned,
  onUploadDiagnosisReport,
  onPublishDiagnosis,
  onCreateQuickOrder,
  documentsWorkplace = null,
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
  onCancelOrder,
  onRecordServiceConsent,
  onRecordAppealsConsent,
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
  orderCode: "DIAG" | "ACCOMP" | "SUPPORT" | "SF_LUMP" | "SF_MONTH";
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
  /** Черновик резюме → доработка ИИ по переписке → поле чата. */
  onPolishBriefDraft?: (draft: string) => void;
  /** Удалить файлы дела (эксперт/админ) — с подтверждением в кабинете. */
  onDeleteDocuments?: (documentIds: string[], label: string) => void;
  /** Удалить черновик проекта обращения (этап 8). */
  onDeleteAppealDraft?: () => void;
  /** Результат ручной сверки периодов (шаг «Сверка сведений»). */
  onRecordFactsReview?: (outcome: "discrepancies" | "no_discrepancies") => void;
  onDismissHint: () => void;
  onTake: () => void;
  onFocusMax: () => void;
  /** Переход на вкладку Финансы по этому делу (счета, не этап pipeline). */
  onOpenFinance?: () => void;
  onRequestReview: () => void;
  /** Только статус пайплайна / проект — без docs-check job. */
  onRequestPipeline?: () => void;
  onCreateTelemost: () => void;
  onSendEmail: () => void;
  onOpenTrackerModal: () => void;
  onOpenSigned: (docId: string, mode?: "open" | "download") => void;
  onUploadDiagnosisReport: (file: File) => void;
  onPublishDiagnosis: (documentId: string) => void;
  onCreateQuickOrder?: (code: "DIAG" | "ACCOMP" | "SUPPORT", amountRub: number) => void;
  /** Проверка текста файлов (2.4) — сразу под блоками этапа «Документы». */
  documentsWorkplace?: ReactNode;
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
  onOrderCode: (v: "DIAG" | "ACCOMP" | "SUPPORT" | "SF_LUMP" | "SF_MONTH") => void;
  onOrderAmount: (v: string) => void;
  onCreateOrder: (e: FormEvent) => void;
  onSendPayLink?: (orderId: string) => void;
  onCopyPayLink?: (orderId: string) => void;
  /** Отменить неоплаченный счёт (крестик в списке этапа оплаты). */
  onCancelOrder?: (orderId: string) => void;
  onRecordServiceConsent: () => void;
  onRecordAppealsConsent?: (decision: "accepted" | "declined" | "thinking") => void;
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
  // Повторные загрузки одного файла (тот же checksum) не считаем отдельными документами.
  const docCount = groupCabinetDocumentsByChecksum(detail.documents).length;
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
  const [accordion, setAccordion] = useState<StageAccordion>(() => initialAccordion(detail.id));
  const [repOpen, setRepOpen] = useState(false);

  function setShowAllPersist(v: boolean) {
    setShowAll(v);
    try {
      localStorage.setItem(SHOW_ALL_KEY, v ? "1" : "0");
    } catch {
      /* ignore */
    }
  }

  const hasFreshCheckResult = Boolean(
    detail.document_check?.result && !detail.document_check?.stale,
  );

  // Свежий результат проверки при этапе «Документы» → по умолчанию открыта предпроверка.
  const defaultOpen: FunnelStageId =
    hasFreshCheckResult && current === "documents" ? "precheck_summary" : current;

  function isExpanded(id: FunnelStageId): boolean {
    if (showAll) return true;
    return openStageOf(accordion, detail.id, defaultOpen) === id;
  }

  function scrollToStage(id: FunnelStageId) {
    // После раскрытия карточки ждём кадр раскладки, иначе «улетает» к верху ленты.
    window.setTimeout(() => {
      document
        .getElementById(`funnel-${id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    }, 50);
  }

  function toggleStage(id: FunnelStageId) {
    setAccordion((previous) => toggleAccordion(previous, detail.id, id, defaultOpen));
    scrollToStage(id);
  }

  function openStage(id: FunnelStageId) {
    setAccordion({ caseId: detail.id, touched: true, open: id });
    scrollToStage(id);
  }

  const stageNav: StageNav = {
    labelOf: (id) => stageById[id]?.label ?? id,
    open: openStage,
  };

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
    if (current === "contact_consents") {
      if (detail.client.max_linked) onFocusMax();
      else onSendEmail();
      return;
    }
    if (current === "documents" || current === "precheck_summary") {
      if (funnel.docsRequiredOk) onRequestReview();
      else onFocusMax();
      return;
    }
    toggleStage(current);
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
            {displayClientFio(detail.client.full_name) ?? "Клиент"} · {caseCatalogLabel(detail.id)}
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
              <div className="case-step-hint-staff">
                <p className="case-step-hint-label">Рекомендация сотруднику</p>
                <p>
                  <strong>{stepHint.source === "deepseek" ? "DeepSeek" : "По этапу"}:</strong>{" "}
                  {stepHint.action}
                </p>
                {stepHint.reason ? <p className="hint">{stepHint.reason}</p> : null}
              </div>
              {stepMessages.length > 0 ? (
                <div className="case-step-hint-client">
                  <p className="case-step-hint-label">Черновики клиенту</p>
                  <div className="case-step-hint-msgs">
                    {stepMessages.map((msg) => (
                      <button
                        key={`${msg.kind}-${msg.text.slice(0, 40)}`}
                        type="button"
                        className="case-chat-btn-chip case-chat-btn-chip--clickable case-chat-btn-chip--client"
                        onClick={() => applyTemplate(msg.text)}
                        title="Подставить в поле чата. Отправка в MAX — отдельно"
                      >
                        <span className="case-step-hint-kind">{KIND_LABEL[msg.kind]}</span>
                        {msg.text}
                      </button>
                    ))}
                  </div>
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
        <StageNavContext.Provider value={stageNav}>
        <div className="funnel-map-head case-funnel-map">
          <h2>Этапы дела</h2>
          <label className="funnel-show-all">
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => setShowAllPersist(e.target.checked)}
            />
            Раскрыть все
          </label>
          <p className="hint">
            Ступени 1–13 по порядку. Нажмите на ступень — раскроются её действия; открыта одна
            ступень. Где нет серверного подтверждения — «не подтверждено».
          </p>
        </div>

        <StageShell
          id="funnel-contact_consents"
          title={stageById.contact_consents.label}
          state={stageById.contact_consents.state}
          reason={stageById.contact_consents.reason}
          summary={stageById.contact_consents.shortSummary}
          expanded={isExpanded("contact_consents")}
          onToggle={() => toggleStage("contact_consents")}
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
                disabled={!canAct("contact_consents") && !showAll}
                onClick={onFocusMax}
                title={stageById.contact_consents.reason}
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
          title={`${stageById.documents.label} · ${docCount}`}
          state={stageById.documents.state}
          reason={stageById.documents.reason}
          summary={stageById.documents.shortSummary}
          expanded={isExpanded("documents")}
          onToggle={() => toggleStage("documents")}
        >
          <ol className="doc-check-blocks">
            <li className="doc-check-block">
              <h4>
                <StepNo n={1} /> Что нужно для проверки
              </h4>
              <p className="hint">
                Чтобы сверить стаж, нужны два документа: выписка ИЛС из СФР (её можно скачать на
                Госуслугах) и трудовая книжка или справки о стаже. Если чего-то нет — подставьте
                клиенту готовый запрос: текст попадёт в поле чата, отправляете вы сами.
              </p>
              <ul className="plain-list doc-kit-list">
                <li>
                  <span className={funnel.hasIls ? "doc-check-ok" : "warning-inline"}>
                    {funnel.hasIls ? "✓ Выписка ИЛС — есть" : "✕ Выписка ИЛС — нет"}
                  </span>
                  {!funnel.hasIls ? (
                    <button
                      type="button"
                      className="linkish"
                      disabled={busy}
                      onClick={() => applyTemplate(DOC_REQUEST_ILS)}
                      title="Подставить запрос ИЛС в поле чата, без автоотправки"
                    >
                      Запросить у клиента
                    </button>
                  ) : null}
                </li>
                <li>
                  <span className={funnel.hasLabor ? "doc-check-ok" : "warning-inline"}>
                    {funnel.hasLabor
                      ? "✓ Трудовая книжка / сведения о стаже — есть"
                      : "✕ Трудовая книжка / сведения о стаже — нет"}
                  </span>
                  {!funnel.hasLabor ? (
                    <button
                      type="button"
                      className="linkish"
                      disabled={busy}
                      onClick={() => applyTemplate(DOC_REQUEST_LABOR)}
                      title="Подставить запрос трудовой в поле чата, без автоотправки"
                    >
                      Запросить у клиента
                    </button>
                  ) : null}
                </li>
              </ul>
            </li>

            <li className="doc-check-block">
              <h4>
                <StepNo n={2} /> Файлы клиента
              </h4>
              <p className="hint">
                Всё, что прислал клиент. Повторные загрузки одного файла свёрнуты в строку «Точный
                дубль». Где стоит «Проверить текст» — откройте и убедитесь, что текст читается: от
                этого зависит точность резюме.
              </p>
              <DocumentsTable
                documents={detail.documents}
                onOpen={onOpenSigned}
                busy={busy}
                onDelete={caps.can_view_ocr ? onDeleteDocuments : undefined}
              />
            </li>

            <li className="doc-check-block">
              <h4>
                <StepNo n={3} /> Чек-лист по документам
              </h4>
              <p className="hint">
                Отмечайте, что запросили и что получили, — так любой сотрудник продолжит дело без
                лишних вопросов к клиенту.
              </p>
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
              ) : (
                <p className="hint">Пунктов пока нет.</p>
              )}
              {caps.can_edit_checklist ? (
                <form className="inline-form" onSubmit={onAddChecklist}>
                  <input
                    value={checklistTitle}
                    onChange={(e) => onChecklistTitle(e.target.value)}
                    placeholder="Например: справка из архива за 1998–2001"
                    required
                  />
                  <button type="submit">Добавить в чек-лист</button>
                </form>
              ) : null}
            </li>
          </ol>

          {documentsWorkplace}
          <p className="hint">
            Комплект на месте? Переходите к проверке — там система разберёт файлы и соберёт резюме
            для клиента.
          </p>
        </StageShell>

        <StageShell
          id="funnel-precheck_summary"
          title={stageById.precheck_summary.label}
          state={stageById.precheck_summary.state}
          reason={stageById.precheck_summary.reason}
          summary={stageById.precheck_summary.shortSummary}
          expanded={isExpanded("precheck_summary")}
          onToggle={() => toggleStage("precheck_summary")}
        >
          <p className="hint">
            Статус: {stageLabel}. ИЛС — {funnel.hasIls ? "есть" : "нет"} · трудовая —{" "}
            {funnel.hasLabor ? "есть" : "нет"}. OCR: {(detail.ocr_texts ?? []).length}. Автоотправки
            клиенту нет.
          </p>
          <CaseWorkRoute
            route={detail.work_route}
            busy={busy}
            onRequestReview={onRequestReview}
            onRequestPipeline={onRequestPipeline}
            onRecordFactsReview={onRecordFactsReview}
            onOpenStage={(id) => openStage(id as FunnelStageId)}
            onRequestDocsFromClient={() => {
              applyTemplate(
                !funnel.hasIls
                  ? DOC_REQUEST_ILS
                  : !funnel.hasLabor
                    ? DOC_REQUEST_LABOR
                    : "Здравствуйте! Для продолжения нужны документы по стажу (ИЛС и/или трудовая). Можно прислать PDF/JPG/PNG в этот чат — специалист увидит. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.",
              );
              onFocusMax();
            }}
            docsCheckPanel={
              <DocumentCheckPanel
                check={detail.document_check}
                busy={busy}
                canManageOrders={caps.can_manage_orders}
                canViewOcr={caps.can_view_ocr}
                orders={detail.orders}
                onApplyChatTemplate={applyTemplate}
                onPolishDraft={onPolishBriefDraft}
                onCreateDiagInvoice={
                  onCreateQuickOrder
                    ? () =>
                        onCreateQuickOrder(
                          "DIAG",
                          detail.document_check?.result?.diag_offer?.amount_rub || 3000,
                        )
                    : undefined
                }
                onSendPayLink={onSendPayLink}
                onUploadDiagnosisReport={onUploadDiagnosisReport}
                onDeleteDocuments={
                  caps.can_view_ocr ? onDeleteDocuments : undefined
                }
                caseDocuments={detail.documents}
              />
            }
          />
          <h3 className="case-subhead">Ранее сохранённые замечания пайплайна</h3>
          <ul className="plain-list">
            {(detail.findings ?? []).length === 0 && (
              <li className="hint">Нет сохранённых замечаний пайплайна</li>
            )}
            {(detail.findings ?? []).map((f, idx) => (
              <li key={`${f.type}-${idx}`}>
                <strong>{f.type}</strong> {f.detail}
              </li>
            ))}
          </ul>
          <h3 className="case-subhead">Помощь в анализе (пайплайн)</h3>
          {detail.analysis_notes ? (
            <pre className="draft">{detail.analysis_notes}</pre>
          ) : (
            <p className="hint">Нет сохранённых notes пайплайна.</p>
          )}
        </StageShell>

        <StageShell
          id="funnel-analysis_payment"
          title={stageById.analysis_payment.label}
          state={stageById.analysis_payment.state}
          reason={stageById.analysis_payment.reason}
          summary={stageById.analysis_payment.shortSummary}
          expanded={isExpanded("analysis_payment")}
          onToggle={() => toggleStage("analysis_payment")}
        >
          {!caps.can_manage_orders ? (
            <p className="hint">Нет права управлять заказами — только просмотр статуса.</p>
          ) : null}
          <p className="hint">
            Учитываем DIAG + сумму + серверный статус. Не любой «оплачено» и не текст чата.
          </p>
          <ul className="plain-list case-orders-list">
            {(detail.orders ?? [])
              .filter((o) => o.package_code === "DIAG")
              .map((o) => (
                <li key={o.id} className="case-order-card">
                  <p>
                    <strong>
                      {o.invoice_number || labelPackage(o.package_code)} · {o.amount_rub} ₽
                    </strong>
                    {" · "}
                    {o.finance_status || o.status}
                  </p>
                  {o.pay_url ? (
                    <p className="hint">
                      <a href={o.pay_url} target="_blank" rel="noreferrer">
                        Ссылка на оплату
                      </a>
                    </p>
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
                      <button type="button" disabled={busy} onClick={() => onSendPayLink(o.id)}>
                        Отправить в MAX
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
          </ul>
          {(detail.orders ?? []).every((o) => o.package_code !== "DIAG") ? (
            <p className="hint">Счёта DIAG ещё нет. Создать можно из резюме (офер) или формы ниже.</p>
          ) : null}
          {caps.can_manage_orders ? (
            <>
              <div className="row-actions">
                <button
                  type="button"
                  className="ghost"
                  disabled={busy}
                  onClick={onRecordServiceConsent}
                >
                  Зафиксировать согласие на услугу
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => applyTemplate(SERVICE_DESCRIPTION_CHAT)}
                >
                  Описание услуги в чат
                </button>
                {onCreateQuickOrder ? (
                  <button
                    type="button"
                    disabled={
                      busy ||
                      (detail.orders ?? []).some(
                        (o) => o.package_code === "DIAG" && o.status === "paid",
                      ) ||
                      (detail.orders ?? []).some(
                        (o) =>
                          o.package_code === "DIAG" &&
                          o.status !== "paid" &&
                          o.status !== "cancelled",
                      )
                    }
                    title={
                      (detail.orders ?? []).some(
                        (o) => o.package_code === "DIAG" && o.status === "paid",
                      )
                        ? "DIAG уже оплачен"
                        : (detail.orders ?? []).some(
                              (o) =>
                                o.package_code === "DIAG" &&
                                o.status !== "paid" &&
                                o.status !== "cancelled",
                            )
                          ? "Счёт DIAG уже есть"
                          : "Создать счёт DIAG 3 000 ₽"
                    }
                    onClick={() => onCreateQuickOrder("DIAG", 3000)}
                  >
                    Счёт DIAG 3 000 ₽
                  </button>
                ) : null}
              </div>
              <form className="inline-form" onSubmit={onCreateOrder}>
                <select
                  value={orderCode}
                  onChange={(e) => onOrderCode(e.target.value as typeof orderCode)}
                >
                  <option value="DIAG">{labelPackage("DIAG")}</option>
                  <option value="ACCOMP">{labelPackage("ACCOMP")}</option>
                  <option value="SUPPORT">{labelPackage("SUPPORT")}</option>
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
                />
                <button type="submit" disabled={busy}>
                  Создать счёт
                </button>
              </form>
            </>
          ) : null}
          {onOpenFinance ? (
            <p className="hint">
              <button type="button" className="linkish" onClick={onOpenFinance}>
                Открыть Финансы по делу
              </button>
            </p>
          ) : null}
        </StageShell>

        <StageShell
          id="funnel-full_analysis"
          title={stageById.full_analysis.label}
          state={stageById.full_analysis.state}
          reason={stageById.full_analysis.reason}
          summary={stageById.full_analysis.shortSummary}
          expanded={isExpanded("full_analysis")}
          onToggle={() => toggleStage("full_analysis")}
        >
          <p className="hint">
            Раздельно: PDF подготовлен ≠ опубликован в кабинете ≠ уведомление доставлено. Черновик
            сообщения не завершает ступень.
          </p>
          <h3 className="case-subhead">PDF результата клиенту</h3>
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
                    <span className="hint"> · PDF подготовлен</span>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="hint">PDF ещё не загружен — статус «не подтверждено» для выдачи.</p>
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
                        "Опубликовать PDF и создать черновики уведомлений? Отправка — только после подтверждения.",
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
              onClick={() => applyTemplate(PLAN_READY_CHAT)}
            >
              Шаблон MAX: результат готов
            </button>
          </div>
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
          ) : (
            <p className="hint">Доставка уведомлений: нет staff-токена / apiBase.</p>
          )}
        </StageShell>

        <StageShell
          id="funnel-appeals_consent"
          title={stageById.appeals_consent.label}
          state={stageById.appeals_consent.state}
          reason={stageById.appeals_consent.reason}
          summary={stageById.appeals_consent.shortSummary}
          expanded={isExpanded("appeals_consent")}
          onToggle={() => toggleStage("appeals_consent")}
        >
          <p className="hint">
            Фиксируем решение по объёму подготовки обращений в audit дела. Не путать с согласием на
            DIAG / ПДн. Текст чата сам по себе статус не меняет.
          </p>
          <div className="row-actions">
            {onRecordAppealsConsent ? (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onRecordAppealsConsent("accepted")}
                >
                  Согласен
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => onRecordAppealsConsent("thinking")}
                >
                  Думает
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={busy}
                  onClick={() => onRecordAppealsConsent("declined")}
                >
                  Отказался
                </button>
              </>
            ) : (
              <p className="hint">Нет обработчика записи согласия.</p>
            )}
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() =>
                applyTemplate(
                  "Здравствуйте! Предлагаем подготовку обращения к СФР (пакет SUPPORT 8 000 ₽ до подачи или ACCOMP 5 000 ₽ на подготовку). Напишите, пожалуйста: согласны / пока думаете / не нужно. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.",
                )
              }
            >
              Спросить согласие в чат
            </button>
          </div>
        </StageShell>

        <StageShell
          id="funnel-appeals_payment"
          title={stageById.appeals_payment.label}
          state={stageById.appeals_payment.state}
          reason={stageById.appeals_payment.reason}
          summary={stageById.appeals_payment.shortSummary}
          expanded={isExpanded("appeals_payment")}
          onToggle={() => toggleStage("appeals_payment")}
        >
          <p className="hint">
            На этом этапе — подготовка обращений ACCOMP 5 000 ₽. Счёт SUPPORT 8 000 ₽ — на этапе
            доп. пакета после ответа СФР. Кнопка создаёт счёт и сразу отправляет ссылку клиенту в
            MAX.
          </p>
          <ul className="plain-list">
            {(detail.orders ?? [])
              .filter(
                (o) =>
                  o.package_code === "ACCOMP" &&
                  Number(o.amount_rub) === 5000 &&
                  o.status !== "cancelled",
              )
              .map((o) => (
                <li key={o.id}>
                  {o.invoice_number || o.package_code} · {o.amount_rub} ₽ ·{" "}
                  {labelOrderStatus(o.status)}
                  {onSendPayLink && o.status !== "paid" ? (
                    <>
                      {" "}
                      <button
                        type="button"
                        className="linkish"
                        disabled={busy}
                        onClick={() => onSendPayLink(o.id)}
                      >
                        Отправить ссылку
                      </button>
                    </>
                  ) : null}
                  {onCancelOrder && o.status !== "paid" ? (
                    <>
                      {" "}
                      <button
                        type="button"
                        className="linkish danger-link"
                        disabled={busy}
                        title="Удалить счёт"
                        aria-label={`Удалить счёт ${o.invoice_number || o.package_code}`}
                        onClick={() => onCancelOrder(o.id)}
                      >
                        ×
                      </button>
                    </>
                  ) : null}
                </li>
              ))}
          </ul>
          {(detail.orders ?? []).every(
            (o) =>
              !(
                o.package_code === "ACCOMP" &&
                Number(o.amount_rub) === 5000 &&
                o.status !== "cancelled"
              ),
          ) ? (
            <p className="hint">Счёта ACCOMP 5 000 ещё нет.</p>
          ) : null}
          {caps.can_manage_orders && onCreateQuickOrder ? (
            <div className="row-actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => onCreateQuickOrder("ACCOMP", 5000)}
                title="Создать счёт и сразу отправить ссылку клиенту в MAX"
              >
                Отправить счёт ACCOMP 5 000 ₽
              </button>
            </div>
          ) : null}
        </StageShell>

        <StageShell
          id="funnel-appeals_documents"
          title={stageById.appeals_documents.label}
          state={stageById.appeals_documents.state}
          reason={stageById.appeals_documents.reason}
          summary={stageById.appeals_documents.shortSummary}
          expanded={isExpanded("appeals_documents")}
          onToggle={() => toggleStage("appeals_documents")}
        >
          <p className="hint">
            Состояния: черновик / готов / передан. Передача «не подтверждена», пока нет серверного
            статуса. DOCX — экспорт текущего draft, не юридический генератор.
          </p>
          {detail.draft ? (
            <div className="stack">
              <div className="row-actions" style={{ justifyContent: "flex-end" }}>
                {onDeleteAppealDraft ? (
                  <button
                    type="button"
                    className="linkish danger-link"
                    disabled={busy}
                    title="Удалить черновик проекта"
                    aria-label="Удалить черновик проекта"
                    onClick={() => onDeleteAppealDraft()}
                  >
                    × Удалить
                  </button>
                ) : null}
              </div>
              <pre className="draft">
                {detail.draft.title}
                {"\n\n"}
                {detail.draft.body}
              </pre>
            </div>
          ) : (
            <p className="hint">Черновика проекта пока нет.</p>
          )}
          <div className="row-actions">
            <button
              type="button"
              disabled={busy || !caps.can_view_ocr}
              onClick={() => (onRequestPipeline ? onRequestPipeline() : onRequestReview())}
            >
              Сформировать / обновить проект
            </button>
            {detail.draft && staffToken && apiBase ? (
              <button
                type="button"
                className="secondary"
                disabled={busy}
                title="Скачать проект обращения в Word"
                onClick={() => {
                  void (async () => {
                    try {
                      const res = await fetch(
                        `${apiBase}/api/portal/admin/cases/${detail.id}/appeal-docx`,
                        { headers: { Authorization: `Bearer ${staffToken}` } },
                      );
                      if (!res.ok) throw new Error(String(res.status));
                      const blob = await res.blob();
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "appeal-draft.docx";
                      a.click();
                      URL.revokeObjectURL(url);
                    } catch {
                      window.alert("Не удалось скачать документ");
                    }
                  })();
                }}
              >
                Скачать документ
              </button>
            ) : null}
            {detail.draft?.body ? (
              <button
                type="button"
                className="ghost"
                onClick={() => applyTemplate(PLAN_READY_CHAT)}
              >
                Подставить сообщение клиенту
              </button>
            ) : null}
          </div>
        </StageShell>

        <StageShell
          id="funnel-submission"
          title={stageById.submission.label}
          state={stageById.submission.state}
          reason={stageById.submission.reason}
          summary={stageById.submission.shortSummary}
          expanded={isExpanded("submission")}
          onToggle={() => toggleStage("submission")}
        >
          <p className="hint">
            Выбор способа ≠ подача. Подтверждение подачи в API отсутствует — «не подтверждено».
            Сотрудник не отмечает подачу автоматически по передаче пакета.
          </p>
          <NotWiredNote label="submission_confirmed_at / адресат" />
          <div className="row-actions">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() =>
                applyTemplate(
                  "Здравствуйте! Пакет готов. Сможете подать через Госуслуги/СФР сами или нужен звонок специалиста для сопровождения до отправки? Напишите удобный вариант. Решение принимает СФР.",
                )
              }
            >
              Спросить: сам / нужен звонок
            </button>
          </div>
        </StageShell>

        <StageShell
          id="funnel-follow_up"
          title={stageById.follow_up.label}
          state={stageById.follow_up.state}
          reason={stageById.follow_up.reason}
          summary={stageById.follow_up.shortSummary}
          expanded={isExpanded("follow_up")}
          onToggle={() => toggleStage("follow_up")}
        >
          <p className="hint">
            Вход — подтверждённая подача (пока «не подтверждено»). Ниже — ручные пресеты срока, не
            авторассылка каждые 3 дня.
          </p>
          <p>
            Сейчас: {nextActionText || "—"} · до {nextActionAt || "—"} · ждём: {waitingOn}
          </p>
          <div className="row-actions">
            {[3, 5, 10, 15, 30].map((days) => (
              <button
                key={days}
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => {
                  const due = new Date();
                  due.setDate(due.getDate() + days);
                  const local = `${due.getFullYear()}-${String(due.getMonth() + 1).padStart(2, "0")}-${String(due.getDate()).padStart(2, "0")}T${String(due.getHours()).padStart(2, "0")}:${String(due.getMinutes()).padStart(2, "0")}`;
                  onNextActionText(
                    days === 3
                      ? "Спросить клиента про уведомления Госуслуг"
                      : `Звонок специалиста (день +${days} от ручного пресета)`,
                  );
                  onNextActionAt(local);
                  onWaitingOn(days === 3 ? "client" : "staff");
                }}
              >
                +{days} дн.
              </button>
            ))}
            <button type="button" disabled={busy} onClick={onSaveNextAction}>
              Сохранить next action
            </button>
          </div>
        </StageShell>

        <StageShell
          id="funnel-response_review"
          title={stageById.response_review.label}
          state={stageById.response_review.state}
          reason={stageById.response_review.reason}
          summary={stageById.response_review.shortSummary}
          expanded={isExpanded("response_review")}
          onToggle={() => toggleStage("response_review")}
        >
          <p className="hint">
            Ответ СФР требует разбора; эскалация не включается автоматически.
          </p>
          {caps.can_confirm_result ? (
            <>
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
                    Прежний размер, ₽
                    <input value={beforeRub} onChange={(e) => onBeforeRub(e.target.value)} required />
                  </label>
                  <label>
                    Новый размер, ₽
                    <input value={afterRub} onChange={(e) => onAfterRub(e.target.value)} required />
                  </label>
                  <label>
                    Единовременная выплата, ₽
                    <input value={lumpRub} onChange={(e) => onLumpRub(e.target.value)} />
                  </label>
                  <button type="submit">Зафиксировать ответ СФР</button>
                </form>
              ) : (
                <p className="hint">Включите переключатель, когда решение СФР получено.</p>
              )}
            </>
          ) : (
            <p className="hint">Нет права фиксировать результат.</p>
          )}
        </StageShell>

        <StageShell
          id="funnel-escalation_package"
          title={stageById.escalation_package.label}
          state={stageById.escalation_package.state}
          reason={stageById.escalation_package.reason}
          summary={stageById.escalation_package.shortSummary}
          expanded={isExpanded("escalation_package")}
          onToggle={() => toggleStage("escalation_package")}
        >
          <p className="hint">
            Вход — основание и согласованный новый объём. ACCOMP 8 000 отдельно от 5 000. Отказ /
            «не требуется» — отдельные исходы (запись согласия пока «не подтверждено»).
          </p>
          <ul className="plain-list">
            {(detail.orders ?? [])
              .filter(
                (o) =>
                  o.package_code === "SUPPORT" ||
                  (o.package_code === "ACCOMP" && Number(o.amount_rub) === 8000),
              )
              .map((o) => (
                <li key={o.id}>
                  {o.invoice_number || o.package_code} · {o.amount_rub} ₽ ·{" "}
                  {labelOrderStatus(o.status)}
                  {o.package_code === "ACCOMP" ? (
                    <span className="hint"> · legacy ACCOMP×8000 (не переклассифицируем)</span>
                  ) : null}
                </li>
              ))}
          </ul>
          {caps.can_manage_orders && onCreateQuickOrder ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => onCreateQuickOrder("SUPPORT", 8000)}
              title="Создать счёт и сразу отправить ссылку клиенту в MAX"
            >
              Отправить счёт SUPPORT 8 000 ₽
            </button>
          ) : null}
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() =>
              applyTemplate(
                "Здравствуйте! По ответу СФР можем оценить доп. пакет (прокуратура/суд) за 8 000 ₽, включая хронологию при необходимости. Напишите: согласны / не требуется / думаете. Решение принимает СФР.",
              )
            }
          >
            Спросить про эскалацию в чат
          </button>
        </StageShell>

        <StageShell
          id="funnel-closure"
          title={stageById.closure.label}
          state={stageById.closure.state}
          reason={stageById.closure.reason}
          summary={stageById.closure.shortSummary}
          expanded={isExpanded("closure")}
          onToggle={() => toggleStage("closure")}
        >
          <p className="hint">
            Закрытие — явное действие сотрудника. Архивный блок ниже не подменяет closed_at.
          </p>
          {caps.can_knowledge_feedback ? (
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
                <button type="submit">Сохранить заметку</button>
              </div>
            </form>
          ) : null}
        </StageShell>
        </StageNavContext.Provider>

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

        <ArchivePrepBlock detail={detail} busy={busy} onSave={onSaveArchivePrep} />
        {onCloseCase ? (
          <CloseCaseBlock detail={detail} busy={busy} onClose={onCloseCase} />
        ) : null}

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
