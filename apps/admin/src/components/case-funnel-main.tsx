"use client";

import {
  deriveFunnel,
  primaryCtaLabel,
  slaHint,
  type FunnelStageId,
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
import { FormEvent, type ReactNode } from "react";

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

function StageMark({ state }: { state: "done" | "current" | "todo" }) {
  if (state === "done") return <span className="funnel-mark funnel-mark--done">✓</span>;
  if (state === "current") return <span className="funnel-mark funnel-mark--current">→</span>;
  return <span className="funnel-mark">○</span>;
}

function Panel({
  title,
  children,
  accent,
  open,
}: {
  title: string;
  children: ReactNode;
  accent?: boolean;
  open?: boolean;
}) {
  if (open === false) {
    return (
      <details className={`panel${accent ? " accent" : ""}`}>
        <summary>{title}</summary>
        {children}
      </details>
    );
  }
  return (
    <div className={`panel${accent ? " accent" : ""}`}>
      <h2>{title}</h2>
      {children}
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
  onOrderCode,
  onOrderAmount,
  onCreateOrder,
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
  orderCode: "DIAG" | "ACCOMP" | "SF_LUMP" | "SF_MONTH";
  orderAmount: string;
  feedbackText: string;
  feedbackQuality: string;
  repEmail: string;
  stepHint: { action: string; reason: string; source: string } | null;
  stepMessages: string[];
  onBack: () => void;
  onNextActionText: (v: string) => void;
  onNextActionAt: (v: string) => void;
  onWaitingOn: (v: string) => void;
  onSaveNextAction: () => void;
  onSuggestStep: () => void;
  onApplyChatMessage: (text: string) => void;
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
  onOrderCode: (v: "DIAG" | "ACCOMP" | "SF_LUMP" | "SF_MONTH") => void;
  onOrderAmount: (v: string) => void;
  onCreateOrder: (e: FormEvent) => void;
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
  const stageLabel = humanCaseStage(detail.pipeline_status, detail.b2c_status);
  const assigned =
    detail.expert_user_id === meUserId
      ? "Я"
      : detail.expert_user_id
        ? "Назначен"
        : "Не назначен";
  const cta = primaryCtaLabel(current, funnel.docsReady);
  const showContactOpen = current === "contact" || !funnel.consentOk || !funnel.channelOk;
  const showDocsOpen = current === "documents" || current === "diagnostics";
  const showDiagOpen = current === "diagnostics" || current === "plan";
  const showPlanOpen = current === "plan";
  const showPayOpen = current === "payment";
  const showResultOpen = current === "result";
  const showFeedbackOpen = current === "feedback";
  const docCount = detail.documents.length;
  const docNeed = 3;
  const auditPreview = detail.audit.slice(0, 5);
  const auditRest = detail.audit.slice(5);

  function runPrimaryCta() {
    if (current === "contact") {
      if (detail.client.max_linked) onFocusMax();
      else onSendEmail();
      return;
    }
    if (current === "documents") {
      if (funnel.docsReady) onRequestReview();
      else onFocusMax();
      return;
    }
    if (current === "diagnostics") {
      onRequestReview();
      return;
    }
    if (current === "plan") {
      onRequestReview();
      return;
    }
    if (current === "payment") {
      /* фокус на блок оплаты */
      document.getElementById("funnel-payment")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    if (current === "result") {
      document.getElementById("funnel-result")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    document.getElementById("funnel-feedback")?.scrollIntoView({ behavior: "smooth" });
  }

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
        <div className="row-actions case-funnel-cta-row">
          <button
            type="button"
            disabled={busy}
            onClick={runPrimaryCta}
            title="Главное действие для текущего этапа воронки"
          >
            {cta}
          </button>
          {!detail.expert_user_id || detail.expert_user_id !== meUserId ? (
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={onTake}
              title="Назначить это дело на себя"
            >
              Взять в работу
            </button>
          ) : null}
          <details className="case-funnel-more">
            <summary className="ghost" title="Служебные ссылки и дополнительные действия">
              ⋮
            </summary>
            <div className="case-funnel-more-menu">
              {detail.client.max_linked ? (
                <button
                  type="button"
                  className="linkish"
                  onClick={onFocusMax}
                  title="Перейти к полю сообщения в чате справа"
                >
                  Написать в MAX
                </button>
              ) : null}
              <a
                href={detail.channels.cabinet_url}
                target="_blank"
                rel="noreferrer"
                title="Открыть личный кабинет клиента для загрузки документов"
              >
                Кабинет клиента
              </a>
              {detail.crm_url ? (
                <a href={detail.crm_url} target="_blank" rel="noreferrer" title="Открыть сделку в amoCRM">
                  amoCRM
                </a>
              ) : null}
              {detail.meeting_url ? (
                <a href={detail.meeting_url} target="_blank" rel="noreferrer" title="Открыть ссылку на Телемост">
                  Телемост
                </a>
              ) : null}
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={onCreateTelemost}
                title="Создать видеовстречу Яндекс Телемост и сохранить ссылку в деле"
              >
                Создать Телемост
              </button>
              <button
                type="button"
                className="linkish"
                disabled={busy}
                onClick={onSendEmail}
                title="Отправить клиенту письмо с запросом документов на email"
              >
                Письмо: документы
              </button>
            </div>
          </details>
        </div>
      </div>

      <div className="case-cards case-funnel-stack">
        <div className="panel accent case-card--wide">
          <h2>1. Текущий шаг</h2>
          <div className="filters">
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
            <button
              type="button"
              disabled={busy}
              onClick={onSaveNextAction}
              title="Сохранить следующий шаг, срок и исполнителя в карточке дела"
            >
              Сохранить
            </button>
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={onSuggestStep}
              title="DeepSeek предложит действие и черновики сообщений. В MAX не отправит — только подставит в чат после вашего выбора"
            >
              {busy ? "DeepSeek думает…" : "Подсказать шаг (DeepSeek)"}
            </button>
          </div>
          <p className="hint">
            Сейчас: {WAITING_LABELS[waitingOn] ?? waitingOn}. Подсказка не отправляет сообщение
            клиенту — только подставляет текст в чат справа.
          </p>
          {stepHint ? (
            <div className="case-step-hint">
              <p>
                <strong>
                  {stepHint.source === "deepseek" ? "DeepSeek" : "По этапу"}:
                </strong>{" "}
                {stepHint.action}
              </p>
              {stepHint.reason ? <p className="hint">{stepHint.reason}</p> : null}
              {stepMessages.length > 0 ? (
                <div className="case-step-hint-msgs">
                  {stepMessages.map((msg) => (
                    <button
                      key={msg.slice(0, 40)}
                      type="button"
                      className="case-chat-btn-chip case-chat-btn-chip--clickable"
                      onClick={() => onApplyChatMessage(msg)}
                      title="Подставить этот текст в поле чата справа. Отправка в MAX — отдельной кнопкой"
                    >
                      Подставить в чат: {msg.length > 70 ? `${msg.slice(0, 70)}…` : msg}
                    </button>
                  ))}
                </div>
              ) : null}
              <button
                type="button"
                className="linkish"
                onClick={onDismissHint}
                title="Скрыть блок подсказки DeepSeek"
              >
                Скрыть подсказку
              </button>
            </div>
          ) : null}
        </div>

        <div className="panel case-card--wide case-funnel-map">
          <h2>Воронка дела</h2>
          <ul className="funnel-grid">
            {funnel.stages.map((s) => (
              <li key={s.id} className={`funnel-item funnel-item--${s.state}`}>
                <StageMark state={s.state} />
                <span>{s.label}</span>
              </li>
            ))}
          </ul>
        </div>

        <Panel title="Контакт и доступ" accent={showContactOpen} open={showContactOpen}>
          <p>
            MAX: {detail.client.max_linked ? "привязан" : "нет"}
            {detail.client.max_user_id ? ` · ${detail.client.max_user_id}` : ""}
            {" · "}Кабинет: {detail.client.web_linked ? "активирован" : "не активирован"}
            {" · "}Согласие на ПДн: {funnel.consentOk ? "получено / не lead" : "нужно"}
            {" · "}Канал: {CHANNEL_LABELS[detail.client.preferred_channel] ?? detail.client.preferred_channel}
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
                onClick={onFocusMax}
                title="Перейти к полю сообщения в чате справа, чтобы написать клиенту в MAX"
              >
                Написать в MAX
              </button>
            ) : null}
            <a
              href={detail.channels.cabinet_url}
              target="_blank"
              rel="noreferrer"
              title="Открыть защищённый кабинет клиента"
            >
              Открыть кабинет
            </a>
          </div>
          <h3 className="case-subhead">Законные представители</h3>
          <ul className="plain-list">
            {(detail.representatives ?? []).length === 0 && <li>Нет</li>}
            {(detail.representatives ?? []).map((rep) => (
              <li key={rep.user_id}>
                {rep.full_name || rep.email || rep.user_id.slice(0, 8)}{" "}
                <button
                  type="button"
                  className="linkish"
                  onClick={() => onRemoveRepresentative(rep.user_id)}
                  title="Снять доступ представителя к этому делу"
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
            <button type="submit" disabled={busy} title="Выдать доступ представителю по email веб-кабинета">
              Выдать доступ
            </button>
          </form>
        </Panel>

        <Panel
          title={`Документы для диагностики · ${Math.min(docCount, docNeed)} из ${docNeed}`}
          accent={showDocsOpen}
          open={showDocsOpen}
        >
          <ul className="plain-list case-doc-checklist">
            <li>
              {funnel.hasIls ? "☑" : "☐"} Выписка ИЛС{" "}
              <button
                type="button"
                className="linkish"
                onClick={() => onApplyChatMessage(
                "Здравствуйте! Для проверки нужна выписка ИЛС с Госуслуг. Загрузите файл только в личном кабинете — не в этот чат. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.",
              )}
                title="Подставить в чат шаблон запроса выписки ИЛС (без автоотправки)"
              >
                Запросить в чат
              </button>
            </li>
            <li>
              {funnel.hasLabor ? "☑" : "☐"} Трудовая / сведения о стаже{" "}
              <button
                type="button"
                className="linkish"
                onClick={() => onApplyChatMessage(
                "Здравствуйте! Подготовьте трудовую книжку или сведения о стаже и загрузите в личный кабинет (не в MAX). Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.",
              )}
                title="Подставить в чат шаблон запроса трудовой (без автоотправки)"
              >
                Запросить в чат
              </button>
            </li>
            <li>☐ Справки — по необходимости после сверки</li>
          </ul>
          <ul className="plain-list">
            {detail.documents.length === 0 && <li className="hint">Файлов в кабинете пока нет</li>}
            {detail.documents.map((doc) => (
              <li key={doc.id}>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => onOpenSigned(doc.id)}
                  title="Открыть документ по защищённой временной ссылке"
                >
                  {doc.storage_path.split("/").pop()}
                </button>
                {doc.doc_type ? ` · ${doc.doc_type}` : ""}
              </li>
            ))}
          </ul>
          <div className="row-actions">
            <a
              href={detail.channels.cabinet_url}
              target="_blank"
              rel="noreferrer"
              title="Открыть кабинет, куда клиент загружает сканы"
            >
              Открыть защищённый кабинет
            </a>
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={onFocusMax}
              title="Написать клиенту напоминание в чате справа"
            >
              Напомнить клиенту
            </button>
            {funnel.docsReady || docCount > 0 ? (
              <button
                type="button"
                disabled={busy}
                onClick={onRequestReview}
                title="Запустить OCR и сверку ИЛС↔трудовая по загруженным документам"
              >
                Запустить проверку
              </button>
            ) : null}
          </div>
        </Panel>

        {caps.can_view_ocr ? (
          <Panel title="Диагностика" accent={showDiagOpen} open={showDiagOpen}>
            <p className="hint">
              Статус: {stageLabel}. Документы: ИЛС — {funnel.hasIls ? "есть" : "нет"} · трудовая —{" "}
              {funnel.hasLabor ? "есть" : "нет"}. OCR: {(detail.ocr_texts ?? []).length} · периоды
              ИЛС: {(detail.ils_periods ?? []).length} · трудовая: {(detail.labor_periods ?? []).length}
            </p>
            <div className="row-actions">
              <button
                type="button"
                disabled={busy}
                onClick={onRequestReview}
                title="Запустить проверку документов: OCR, периоды, замечания"
              >
                Проверить документы
              </button>
            </div>
            <h3 className="case-subhead">Замечания / расхождения</h3>
            <ul className="plain-list">
              {(detail.findings ?? []).length === 0 && <li className="hint">Пока нет — запустите проверку</li>}
              {(detail.findings ?? []).map((f, idx) => (
                <li key={`${f.type}-${idx}`}>
                  <strong>{f.type}</strong> {f.detail}
                </li>
              ))}
            </ul>
            <h3 className="case-subhead">Обоснование аналитика (DeepSeek)</h3>
            {detail.analysis_notes ? (
              <pre className="draft">{detail.analysis_notes}</pre>
            ) : (
              <p className="hint">Появится после проверки. Не заменяет специалиста.</p>
            )}
          </Panel>
        ) : null}

        <Panel
          title="План действий и проект обращения"
          accent={showPlanOpen}
          open={showPlanOpen || Boolean(detail.draft)}
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
              disabled={busy || !caps.can_view_ocr}
              onClick={onRequestReview}
              title="Сформировать или обновить проект обращения (DeepSeek). Нужна проверка специалистом"
            >
              Сформировать / обновить проект
            </button>
            {detail.draft?.body ? (
              <button
                type="button"
                className="ghost"
                onClick={() =>
                  onApplyChatMessage(
                    "Подготовили проект обращения и план. Откройте личный кабинет — там текст и чек-лист. Мы расскажем по шагам, но подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.",
                  )
                }
                title="Подставить в чат безопасное сообщение без ПДн и без вложений"
              >
                Отправить клиенту в чат (без ПДн)
              </button>
            ) : null}
          </div>
        </Panel>

        {caps.can_manage_orders ? (
          <div id="funnel-payment">
            <Panel title="Услуга и оплата" accent={showPayOpen} open={showPayOpen}>
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
              <form className="inline-form" onSubmit={onCreateOrder}>
                <select
                  value={orderCode}
                  onChange={(e) => onOrderCode(e.target.value as typeof orderCode)}
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
                />
                <button type="submit" title="Создать счёт по выбранной услуге и сумме">
                  Создать счёт
                </button>
              </form>
              <p className="hint">Сумма по выбранной услуге / договору. Не путать с решением СФР.</p>
            </Panel>
          </div>
        ) : null}

        {caps.can_confirm_result ? (
          <div id="funnel-result">
            <Panel title="Ответ СФР и итог по делу" accent={showResultOpen} open={showResultOpen}>
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
                  <input value={lumpRub} onChange={(e) => onLumpRub(e.target.value)} />
                </label>
                <button type="submit" title="Сохранить фактические суммы из решения СФР в деле">
                  Зафиксировать ответ СФР
                </button>
              </form>
              <p className="hint">Только факты из решения СФР, не цена услуги сервиса.</p>
            </Panel>
          </div>
        ) : null}

        {caps.can_knowledge_feedback ? (
          <div id="funnel-feedback">
            <Panel
              title="Обезличенный вывод в базу знаний"
              accent={showFeedbackOpen}
              open={showFeedbackOpen}
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
                  <button type="submit" title="Сохранить обезличенный вывод в базу знаний (без ПДн)">
                    Сохранить
                  </button>
                </div>
              </form>
            </Panel>
          </div>
        ) : null}

        <Panel title="Чек-лист" open={false}>
          <ul className="plain-list">
            {detail.checklist_items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="linkish"
                  disabled={!caps.can_edit_checklist}
                  onClick={() => onToggleChecklist(item.id, item.status)}
                  title="Переключить статус пункта чек-листа"
                >
                  [{labelChecklistStatus(item.status)}] {item.title}
                </button>
                <span className="hint"> · {labelChecklistOwner(item.owner)}</span>
              </li>
            ))}
          </ul>
          {caps.can_edit_checklist ? (
            <form className="inline-form" onSubmit={onAddChecklist}>
              <input
                value={checklistTitle}
                onChange={(e) => onChecklistTitle(e.target.value)}
                placeholder="Новый пункт"
                required
              />
              <button type="submit" title="Добавить новый пункт в чек-лист дела">
                Добавить
              </button>
            </form>
          ) : null}
        </Panel>

        {caps.can_edit_pipeline ? (
          <Panel title="Этап пайплайна (технический)" open={false}>
            <div className="inline-form">
              <select value={pipelineStatus} onChange={(e) => onPipelineStatus(e.target.value)}>
                {pipelineStageOptions().map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={onSavePipeline}
                title="Сохранить технический код этапа пайплайна"
              >
                Сохранить этап
              </button>
            </div>
          </Panel>
        ) : null}

        <details className="panel service-details case-card--wide">
          <summary>Служебное · журнал</summary>
          <p className="hint">ID: {detail.id}</p>
          <p>
            pipeline={detail.pipeline_status} · b2c={detail.b2c_status}
          </p>
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

// silence unused type export for eslint if FunnelStageId only used in derive
export type { FunnelStageId };
