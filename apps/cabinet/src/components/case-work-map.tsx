"use client";

import { type ChangeEvent, useRef } from "react";

export type WorkSlot = {
  key: string;
  title: string;
  need: string;
  need_label: string;
  doc_type?: string | null;
  status: string;
  status_label: string;
  added_at?: string | null;
  document_id?: string | null;
  can_replace?: boolean;
  can_delete?: boolean;
};

export type ClientWork = {
  status_key: string;
  status_label: string;
  status_hint: string;
  now_need: string;
  cta_key: string;
  cta_label: string;
  sla_note: string;
  required_uploaded: number;
  required_total: number;
  consent_ok: boolean;
  stages: { n: number; title: string; hint: string; state: string }[];
  documents: WorkSlot[];
  order: {
    state: string;
    title: string;
    amount_rub: number;
    status_label: string;
    can_pay: boolean;
    order_id?: string | null;
    includes: string[];
  };
  result: { ready: boolean; document_id?: string | null; added_at?: string | null };
  next_actions: string[];
  ils_howto_url: string;
  offer_url: string;
};

type Props = {
  caseNumber: string;
  work: ClientWork;
  busy?: boolean;
  maxHref: string;
  warning: string;
  onConsent: () => void;
  onUpload: (file: File, docType?: string) => void;
  onDelete: (documentId: string) => void;
  onPay: (orderId: string) => void;
  onDownloadResult: (documentId: string) => void;
};

function mark(state: string) {
  if (state === "done") return "✓";
  if (state === "current") return "●";
  return "○";
}

function firstUploadSlot(work: ClientWork): WorkSlot | undefined {
  return (
    work.documents.find((row) => row.status === "missing" || row.status === "reupload") ||
    work.documents.find((row) => row.status === "not_needed") ||
    work.documents[0]
  );
}

export function CaseWorkMap({
  caseNumber,
  work,
  busy,
  maxHref,
  warning,
  onConsent,
  onUpload,
  onDelete,
  onPay,
  onDownloadResult,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const pendingSlot = useRef<WorkSlot | null>(null);

  function pickFile(next: WorkSlot) {
    pendingSlot.current = next;
    const input = fileRef.current;
    if (input) {
      input.dataset.slotKey = next.key;
      input.click();
    }
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const slotKey = event.currentTarget.dataset.slotKey;
    event.target.value = "";
    const chosen =
      work.documents.find((row) => row.key === slotKey) || pendingSlot.current || firstUploadSlot(work);
    pendingSlot.current = null;
    if (!file) return;
    onUpload(file, chosen?.doc_type || undefined);
  }

  const cta = work.cta_key;
  const uploadSlot = firstUploadSlot(work);
  const waiting = work.next_actions.length === 0 && (cta === "wait" || cta === "upload");
  const diagDone = work.result.ready;
  const diagNow = ["docs_review", "diagnosis"].includes(work.status_key);

  return (
    <div className="case-map">
      <input
        ref={fileRef}
        type="file"
        className="sr-only"
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
        disabled={busy}
        onChange={onFile}
      />

      <header className="case-hero panel accent">
        <p className="case-hero-kicker">Дело ПС-{caseNumber}</p>
        <p className="case-hero-status" aria-live="polite">
          Статус: <strong>{work.status_label}</strong>
        </p>
        <p className="case-hero-need">
          {waiting ? (
            <strong>Сейчас от вас ничего не требуется.</strong>
          ) : (
            <>
              Сейчас нужно от вас:
              <strong> {work.now_need}</strong>
            </>
          )}
        </p>
        {cta === "consent" ? (
          <button type="button" disabled={busy} onClick={onConsent}>
            {work.cta_label}
          </button>
        ) : null}
        {cta === "upload" && uploadSlot ? (
          <button type="button" disabled={busy} onClick={() => pickFile(uploadSlot)}>
            {work.cta_label}
          </button>
        ) : null}
        {cta === "pay" && work.order.order_id ? (
          <button type="button" disabled={busy} onClick={() => onPay(work.order.order_id!)}>
            {work.cta_label}
          </button>
        ) : null}
        {cta === "wait" ? (
          <a className="button-link" href={maxHref} target="_blank" rel="noopener noreferrer">
            {work.cta_label}
          </a>
        ) : null}
        {(cta === "result" || cta === "done") && work.result.document_id ? (
          <button type="button" disabled={busy} onClick={() => onDownloadResult(work.result.document_id!)}>
            {work.cta_label}
          </button>
        ) : null}
        <p className="hint">{work.sla_note}</p>
        <ul className="case-ticks">
          <li className={work.consent_ok ? "done" : ""}>
            {work.consent_ok ? "✓" : "○"} Согласие {work.consent_ok ? "получено" : "нужно подтвердить"}
          </li>
          <li className={work.required_uploaded >= work.required_total ? "done" : "current"}>
            {work.required_uploaded >= work.required_total ? "✓" : "●"} Документы — {work.required_uploaded} из{" "}
            {work.required_total}
          </li>
          <li className={diagDone ? "done" : diagNow ? "current" : ""}>
            {diagDone ? "✓" : diagNow ? "●" : "○"} Диагностика{" "}
            {diagDone
              ? "готова"
              : diagNow
                ? "идёт проверка комплекта"
                : "начнётся после проверки документов"}
          </li>
          <li className={work.result.ready ? "done" : ""}>
            {work.result.ready ? "✓" : "○"} Результат {work.result.ready ? "доступен здесь" : "будет доступен здесь"}
          </li>
        </ul>
      </header>

      <section className="panel">
        <h2>Как идёт работа</h2>
        <ol className="work-progress">
          {work.stages.map((stage) => (
            <li key={stage.n} className={stage.state}>
              <span className="mark" aria-hidden>
                {mark(stage.state)}
              </span>
              <div>
                <strong>{stage.title}</strong>
                <p className="hint">{stage.hint}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel my-docs" id="docs-table">
        <div className="docs-table-head">
          <h2>Мои документы</h2>
          <p className="docs-count">
            Загружено: {work.required_uploaded} из {work.required_total} обязательных
          </p>
        </div>
        <div className="my-docs-table-wrap">
          <table className="my-docs-table">
            <thead>
              <tr>
                <th>Документ</th>
                <th>Нужен для работы</th>
                <th>Статус</th>
                <th>Когда добавлен</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {work.documents.map((row) => (
                <tr key={row.key}>
                  <td>{row.title}</td>
                  <td>{row.need_label}</td>
                  <td>
                    <span className={`doc-status doc-status--${row.status}`}>{row.status_label}</span>
                    {row.status === "reupload" ? (
                      <p className="hint">Файл не удалось прочитать. Загрузите более чёткое фото или PDF.</p>
                    ) : null}
                  </td>
                  <td>{row.added_at || "—"}</td>
                  <td>
                    <SlotActions
                      row={row}
                      busy={busy}
                      onPick={() => pickFile(row)}
                      onDelete={onDelete}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="my-docs-cards">
          {work.documents.map((row) => (
            <li key={row.key} className="my-doc-card">
              <div className="my-doc-card-top">
                <strong>{row.title}</strong>
                <span>{row.need_label}</span>
              </div>
              <p>
                Статус: <span className={`doc-status doc-status--${row.status}`}>{row.status_label}</span>
              </p>
              {row.added_at ? <p className="hint">Добавлено: {row.added_at}</p> : null}
              {row.status === "reupload" ? (
                <p className="hint">Файл не удалось прочитать. Загрузите более чёткое фото или PDF.</p>
              ) : null}
              <SlotActions row={row} busy={busy} onPick={() => pickFile(row)} onDelete={onDelete} />
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Ваш заказ</h2>
        {work.order.state === "not_agreed" ? (
          <p>Услуга ещё не согласована. Сначала специалист объяснит состав работ и стоимость.</p>
        ) : (
          <>
            <p>
              <strong>Услуга:</strong> {work.order.title}
            </p>
            <p>Что входит:</p>
            <ul className="plain-list">
              {work.order.includes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p>
              Стоимость: <strong>{work.order.amount_rub.toLocaleString("ru-RU")} ₽</strong>
            </p>
            <p>
              Статус оплаты: <strong>{work.order.status_label}</strong>
            </p>
            {work.order.can_pay && work.order.order_id ? (
              <p className="home-actions">
                <button type="button" disabled={busy} onClick={() => onPay(work.order.order_id!)}>
                  Оплатить безопасно
                </button>
                <a className="secondary" href={maxHref} target="_blank" rel="noopener noreferrer">
                  Задать вопрос об услуге
                </a>
              </p>
            ) : (
              <p className="home-actions">
                <a className="secondary" href={work.offer_url} target="_blank" rel="noreferrer">
                  Открыть условия услуги
                </a>
              </p>
            )}
          </>
        )}
        <p className="hint">{warning}</p>
      </section>

      <section className="panel">
        <h2>Результат диагностики</h2>
        {work.result.ready && work.result.document_id ? (
          <>
            <p>
              Статус: <strong>Готово</strong>
            </p>
            {work.result.added_at ? <p>Подготовлено: {work.result.added_at}</p> : null}
            <p className="hint">
              Проверены предоставленные документы. Короткий PDF — в кабинете. Решение о пенсии принимает СФР.
            </p>
            <p className="home-actions">
              <button type="button" disabled={busy} onClick={() => onDownloadResult(work.result.document_id!)}>
                Открыть результат
              </button>
              <button type="button" className="secondary" disabled={busy} onClick={() => onDownloadResult(work.result.document_id!)}>
                Скачать PDF
              </button>
              <a className="secondary" href={maxHref} target="_blank" rel="noopener noreferrer">
                Задать вопрос специалисту
              </a>
            </p>
          </>
        ) : (
          <p className="hint">Результат появится здесь после завершения диагностики.</p>
        )}
      </section>

      <section className="panel">
        <h2>Ваши действия</h2>
        {work.next_actions.length === 0 ? (
          <>
            <p>
              <strong>Сейчас от вас ничего не требуется.</strong>
            </p>
            <p>Мы проверяем комплект документов. Следующее сообщение придёт в MAX.</p>
          </>
        ) : (
          <ol className="plain-list next-actions">
            {work.next_actions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        )}
        <p className="home-actions">
          <a className="secondary" href={work.ils_howto_url} target="_blank" rel="noreferrer">
            Как получить выписку ИЛС
          </a>
          <a className="button-link" href={maxHref} target="_blank" rel="noopener noreferrer">
            Открыть чат MAX
          </a>
        </p>
      </section>

      <section className="panel">
        <h2>Вопросы по делу — в чате MAX</h2>
        <p>Ответ специалиста придёт в MAX, а не в форму на этой странице.</p>
        <a className="button-link" href={maxHref} target="_blank" rel="noopener noreferrer">
          Открыть чат MAX
        </a>
      </section>

      <p className="hint safety-note">
        Не отправляйте документы в чат. Файлы — только в этом кабинете. {warning}
      </p>
    </div>
  );
}

function SlotActions({
  row,
  busy,
  onPick,
  onDelete,
}: {
  row: WorkSlot;
  busy?: boolean;
  onPick: () => void;
  onDelete: (id: string) => void;
}) {
  if (row.status === "accepted") {
    return <span className="hint">{row.added_at ? `Проверено: ${row.added_at}` : "Принят"}</span>;
  }
  if (row.status === "not_needed") {
    return (
      <button type="button" className="linkish" disabled={busy} onClick={onPick}>
        Добавить
      </button>
    );
  }
  if (row.status === "awaiting" || row.status === "reupload") {
    return (
      <span className="slot-actions">
        <button type="button" className="linkish" disabled={busy} onClick={onPick}>
          Заменить файл
        </button>
        {row.can_delete && row.document_id ? (
          <button
            type="button"
            className="linkish"
            disabled={busy}
            onClick={() => {
              if (window.confirm("Удалить файл до проверки специалистом?")) onDelete(row.document_id!);
            }}
          >
            Удалить до проверки
          </button>
        ) : null}
      </span>
    );
  }
  return (
    <button type="button" disabled={busy} onClick={onPick}>
      Загрузить
    </button>
  );
}
