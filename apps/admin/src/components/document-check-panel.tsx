"use client";

import { StepNo } from "@/components/step-number";
import {
  buildCheckView,
  type CheckBriefItem,
  type CheckResultInput,
} from "@/lib/document-check-view";
import {
  formatAskClientNextStepsTemplate,
  formatBriefChatTemplate,
  type HonestBriefForChat,
} from "@/lib/format-brief-chat";

type HonestBrief = HonestBriefForChat & {
  current?: boolean;
  stale_reason?: string;
};

export type DocumentCheck = {
  status?: string;
  status_label?: string;
  stale?: boolean;
  current_stage?: string | null;
  last_error?: string | null;
  result?:
    | (Omit<CheckResultInput, "honest_brief"> & {
        ocr_allowed?: boolean;
        honest_brief?: HonestBrief | null;
        diag_offer?: { allowed?: boolean; amount_rub?: number } | null;
      })
    | null;
};

type CheckOrder = { id: string; package_code: string; status: string };

function ItemList({ items, showBasis = false }: { items: CheckBriefItem[]; showBasis?: boolean }) {
  return (
    <ul className="plain-list">
      {items.slice(0, 3).map((item, idx) => (
        <li key={`${item.evidence || "x"}-${idx}`}>
          {item.text || "—"}
          {showBasis && item.basis ? <span className="hint"> — {item.basis}</span> : null}
        </li>
      ))}
    </ul>
  );
}

export function DocumentCheckPanel({
  check,
  busy,
  canManageOrders,
  canViewOcr,
  orders,
  onApplyChatTemplate,
  onPolishDraft,
  onCreateDiagInvoice,
  onSendPayLink,
  onUploadDiagnosisReport,
}: {
  check: DocumentCheck | null | undefined;
  busy?: boolean;
  canManageOrders?: boolean;
  canViewOcr?: boolean;
  orders?: CheckOrder[];
  onApplyChatTemplate: (text: string) => void;
  /** Доработка черновика ИИ по переписке; без него — шаблон как есть. */
  onPolishDraft?: (draft: string) => void;
  onCreateDiagInvoice?: () => void;
  onSendPayLink?: (orderId: string) => void;
  onUploadDiagnosisReport?: (file: File) => void;
}) {
  if (!check) {
    return (
      <p className="hint">
        Нажмите «Проверить документы» — система разберёт комплект за несколько секунд и соберёт
        краткое резюме для клиента.
      </p>
    );
  }
  const r = check.result;
  const diagOrders = (orders ?? []).filter((o) => o.package_code === "DIAG");
  const diagPaid = diagOrders.some((o) => o.status === "paid");
  const diagOpen = diagPaid
    ? undefined
    : diagOrders.find((o) => o.status !== "paid" && o.status !== "cancelled");
  const brief = r?.honest_brief ?? null;
  // Офер — только при расхождении из документов (старые результаты разрешали его по анкете).
  const offerAllowed =
    Boolean(r?.diag_offer?.allowed) && (brief?.items ?? []).some((i) => i.evidence === "docs");
  const amount = r?.diag_offer?.amount_rub ?? brief?.offer_amount_rub ?? 3000;
  const view = r ? buildCheckView(r, { offerAllowed, diagPaid, diagAmountRub: amount }) : null;
  const running = check.status === "queued" || check.status === "running";
  const askFirst =
    view?.next.kind === "clarify" ||
    view?.next.kind === "ask_docs" ||
    view?.next.kind === "fix_files";

  const toChat = onPolishDraft ?? onApplyChatTemplate;

  function applyBrief() {
    if (!brief) return;
    toChat(
      formatBriefChatTemplate(brief, { diagAllowed: offerAllowed, diagPaid, diagAmountRub: amount }),
    );
  }

  function applyAsk() {
    toChat(
      formatAskClientNextStepsTemplate(brief, {
        diagAllowed: offerAllowed,
        diagPaid,
        diagAmountRub: amount,
      }),
    );
  }

  return (
    <div className="document-check-result">
      <p className="doc-check-status">
        Статус проверки: <strong>{check.status_label || check.status}</strong>
        {check.stale ? (
          <span className="hint warning-inline">
            {" "}
            · набор документов изменился — запустите проверку снова, иначе резюме устарело
          </span>
        ) : null}
      </p>
      {running ? (
        <p className="hint">Проверяем комплект… обычно это занимает несколько секунд.</p>
      ) : null}
      {check.last_error ? (
        <p className="hint warning-inline">
          Проверка не завершилась ({check.last_error}). Нажмите «Проверить документы» ещё раз.
        </p>
      ) : null}

      {r && view ? (
        <ol className="doc-check-blocks">
          <li className="doc-check-block">
            <h4>
              <StepNo n={1} /> Что получили
            </h4>
            <p>
              Файлов: <strong>{view.kit.unique}</strong>
              {view.kit.duplicates > 0
                ? ` (ещё ${view.kit.duplicates} — повторные загрузки, в таблице свёрнуты)`
                : ""}
              .
            </p>
            <p>Распознаны: {view.kit.types.length > 0 ? view.kit.types.join(", ") : "тип не определён"}.</p>
            {view.kit.hasCore ? (
              <p className="doc-check-ok">
                ✓ Базовый комплект на месте: выписка ИЛС и трудовая книжка — можно сверять.
              </p>
            ) : view.kit.missing.length > 0 ? (
              <p className="warning-inline">Не хватает: {view.kit.missing.join(", ")}.</p>
            ) : (
              <p className="hint">
                Для сверки нужны выписка ИЛС и трудовая книжка (или справки о стаже).
              </p>
            )}
          </li>

          <li className="doc-check-block">
            <h4>
              <StepNo n={2} /> Что удалось прочитать
            </h4>
            <p>
              Текст извлечён у <strong>{view.read.textOk}</strong> из {view.read.total} файлов.
            </p>
            {view.read.unreadable.length > 0 ? (
              <p className="warning-inline">
                Не прочитан: {view.read.unreadable.join(", ")} — скан или фото без текстового слоя.
                {r.ocr_allowed ? "" : " Автораспознавание сканов сейчас выключено."}
              </p>
            ) : (
              <p className="doc-check-ok">✓ Все файлы читаются.</p>
            )}
            {view.read.manual.length > 0 ? (
              <p className="hint">Тип не определён автоматически: {view.read.manual.join(", ")}.</p>
            ) : null}
          </li>

          <li className="doc-check-block">
            <h4>
              <StepNo n={3} /> Что видно по сути
            </h4>
            {brief && brief.current === false && brief.stale_reason ? (
              <p className="hint warning-inline">{brief.stale_reason}</p>
            ) : null}
            {view.compare.ran ? <p className="hint">{view.compare.summary}</p> : null}
            {view.findings.docs.length > 0 ? (
              <>
                <p className="doc-check-group">Подтверждено документами</p>
                <ItemList items={view.findings.docs} showBasis />
              </>
            ) : view.compare.ran ? null : (
              <p className="hint">
                {view.compare.reason
                  ? `${view.compare.reason} Темы ниже — повод для разговора с клиентом, а не вывод.`
                  : "Автоматическая сверка периодов ИЛС и трудовой пока не проводилась — подтверждённых расхождений в данных нет. Темы ниже — повод для разговора с клиентом, а не вывод."}
              </p>
            )}
            {view.findings.questionnaire.length > 0 ? (
              <>
                <p className="doc-check-group">Требует проверки — из анкеты</p>
                <ItemList items={view.findings.questionnaire} />
              </>
            ) : null}
            {view.findings.client.length > 0 ? (
              <>
                <p className="doc-check-group">Со слов клиента</p>
                <ItemList items={view.findings.client} />
              </>
            ) : null}
            {view.findings.docs.length +
              view.findings.questionnaire.length +
              view.findings.client.length ===
            0 ? (
              <p className="hint">Тем для уточнения нет.</p>
            ) : null}
          </li>

          <li className={`doc-check-block doc-check-next doc-check-next--${view.next.kind}`}>
            <h4>
              <StepNo n={4} /> Что делаем дальше
            </h4>
            <p>
              <strong>{view.next.title}</strong>
            </p>
            <p>{view.next.text}</p>
            <div className="row-actions doc-check-actions">
              {askFirst ? (
                <button type="button" disabled={busy} onClick={applyAsk}>
                  {view.next.kind === "clarify"
                    ? "Спросить клиента о периодах"
                    : "Написать клиенту"}
                </button>
              ) : null}
              {brief ? (
                <button
                  type="button"
                  className={askFirst || view.next.kind === "paid" ? "secondary" : undefined}
                  disabled={busy}
                  title="ИИ доработает резюме по переписке и подставит в поле чата. В MAX само не отправляется"
                  onClick={applyBrief}
                >
                  Подставить резюме в чат
                </button>
              ) : null}
              {offerAllowed && !diagPaid && canManageOrders && onCreateDiagInvoice ? (
                <button
                  type="button"
                  className="secondary"
                  disabled={busy || Boolean(diagOpen)}
                  onClick={() => onCreateDiagInvoice()}
                  title={diagOpen ? "Счёт DIAG уже есть — отправьте ссылку" : "Создать счёт DIAG"}
                >
                  Счёт на диагностику {amount.toLocaleString("ru-RU")} ₽
                </button>
              ) : null}
              {offerAllowed && diagOpen && onSendPayLink ? (
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => onSendPayLink(diagOpen.id)}
                >
                  Отправить ссылку на оплату в MAX
                </button>
              ) : null}
              {view.next.kind === "paid" && onUploadDiagnosisReport ? (
                <label className="secondary" style={{ cursor: busy ? "wait" : "pointer" }}>
                  Загрузить PDF разбора
                  <input
                    type="file"
                    accept="application/pdf,.pdf"
                    hidden
                    disabled={busy || !canViewOcr}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (file) onUploadDiagnosisReport(file);
                    }}
                  />
                </label>
              ) : null}
            </div>
          </li>
        </ol>
      ) : null}

      <p className="hint doc-check-footer">
        {brief?.disclaimer ||
          "Это предварительная автоматическая проверка комплекта, а не юридическое заключение."}{" "}
        Решение об учёте стажа принимает СФР.
      </p>
    </div>
  );
}
