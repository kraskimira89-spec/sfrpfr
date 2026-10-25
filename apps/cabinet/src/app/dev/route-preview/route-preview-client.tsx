"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CabinetCaseLayout } from "@/components/cabinet-case-layout";
import { CaseWorkMap, type ClientWork } from "@/components/case-work-map";
import { ClientCaseChatPanel } from "@/components/client-case-chat-panel";
import { resolveRoutePrimaryAction } from "@/lib/case-route";

type ScenarioId =
  | "consent"
  | "upload"
  | "waiting"
  | "reupload"
  | "contract"
  | "pay"
  | "result"
  | "unavailable"
  | "unknown";

const WARNING = "Решение принимает СФР. Результат не гарантирован.";

function stages(current: number): ClientWork["stages"] {
  return [1, 2, 3, 4, 5].map((n) => ({
    n,
    title: String(n),
    hint: "",
    state: n < current ? "done" : n === current ? "current" : "todo",
  }));
}

function workFor(id: ScenarioId): ClientWork {
  const baseDocs: ClientWork["documents"] = [
    {
      key: "ils",
      title: "Выписка ИЛС",
      need: "required",
      need_label: "Обязательно",
      doc_type: "ils",
      status: "missing",
      status_label: "Нужно загрузить",
    },
    {
      key: "labor",
      title: "Трудовая книжка",
      need: "required",
      need_label: "Обязательно",
      doc_type: "workbook",
      status: "accepted",
      status_label: "Принят для текущего этапа",
      added_at: "23 октября, 18:40",
      document_id: "doc-labor",
    },
  ];
  const order = {
    state: "not_agreed",
    title: "Диагностика",
    package_code: "DIAG",
    amount_rub: 3000,
    status_label: "Услуга ещё не согласована",
    can_pay: false,
    order_id: null as string | null,
    includes: ["сверка ИЛС и трудовой"],
  };
  const result = { ready: false, document_id: null as string | null, added_at: null as string | null };

  switch (id) {
    case "consent":
      return {
        status_key: "consent",
        status_label: "Нужно согласие",
        status_hint: "Подтвердите согласие",
        now_need: "Подтвердить согласие на обработку персональных данных",
        cta_key: "consent",
        cta_label: "Даю согласие на обработку персональных данных",
        sla_note: "После согласия можно загрузить файлы.",
        required_uploaded: 0,
        required_total: 2,
        consent_ok: false,
        stages: stages(1),
        documents: baseDocs.map((d) => ({ ...d, status: "missing", added_at: null, document_id: null })),
        order,
        result,
        next_actions: ["Подтвердить согласие"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "waiting":
      return {
        status_key: "docs_review",
        status_label: "Документы на проверке",
        status_hint: "Проверяем комплект",
        now_need: "Сейчас от вас ничего не требуется",
        cta_key: "wait",
        cta_label: "Задать вопрос в чате",
        sla_note: "Срок проверки комплекта: до 1 рабочего дня.",
        required_uploaded: 2,
        required_total: 2,
        consent_ok: true,
        stages: stages(3),
        documents: [
          {
            ...baseDocs[0]!,
            status: "awaiting",
            status_label: "Документ получен. Проверим его пригодность",
            added_at: "25 октября, 12:00",
            document_id: "doc-ils",
          },
          {
            ...baseDocs[1]!,
            status: "awaiting",
            status_label: "Документ получен. Проверим его пригодность",
            added_at: "25 октября, 12:05",
          },
        ],
        order: { ...order, state: "paid", can_pay: false, status_label: "Оплата получена" },
        result,
        next_actions: [],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "reupload":
      return {
        status_key: "need_info",
        status_label: "Нужны уточнения",
        status_hint: "Нужен более читаемый файл",
        now_need: "Загрузить Выписка ИЛС",
        cta_key: "upload",
        cta_label: "Перейти к загрузке документов",
        sla_note: "Загрузите более чёткий файл.",
        required_uploaded: 1,
        required_total: 2,
        consent_ok: true,
        stages: stages(2),
        documents: [
          {
            ...baseDocs[0]!,
            status: "reupload",
            status_label: "Нужно загрузить повторно",
            added_at: "25 октября, 11:00",
            document_id: "doc-ils-old",
            can_replace: true,
          },
          baseDocs[1]!,
        ],
        order,
        result,
        next_actions: ["Загрузить: Выписка ИЛС"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "contract":
      return {
        status_key: "docs_review",
        status_label: "Документы на проверке",
        status_hint: "Комплект на проверке",
        now_need: "Принять условия и получить счёт на диагностику",
        cta_key: "contract",
        cta_label: "Принять условия и получить счёт на диагностику",
        sla_note: "После принятия условий будет сформирован счёт.",
        required_uploaded: 2,
        required_total: 2,
        consent_ok: true,
        stages: stages(3),
        documents: [
          {
            ...baseDocs[0]!,
            status: "awaiting",
            status_label: "Документ получен. Проверим его пригодность",
            added_at: "25 октября, 12:00",
            document_id: "doc-ils",
          },
          {
            ...baseDocs[1]!,
            status: "awaiting",
            status_label: "Документ получен. Проверим его пригодность",
            added_at: "25 октября, 12:05",
          },
        ],
        order,
        result,
        next_actions: ["Принять условия и получить счёт на диагностику"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "pay":
      return {
        status_key: "docs_review",
        status_label: "Документы на проверке",
        status_hint: "Оплата диагностики",
        now_need: "Оплатить диагностику",
        cta_key: "pay",
        cta_label: "Оплатить диагностику — 3 000 ₽",
        sla_note: "Оплата через ЮKassa.",
        required_uploaded: 2,
        required_total: 2,
        consent_ok: true,
        stages: stages(3),
        documents: baseDocs.map((d) => ({
          ...d,
          status: "awaiting",
          status_label: "Документ получен. Проверим его пригодность",
          added_at: "25 октября, 12:00",
          document_id: `doc-${d.key}`,
        })),
        order: {
          ...order,
          state: "pay",
          can_pay: true,
          order_id: "ord-preview-1",
          status_label: "Ожидает оплаты",
        },
        result,
        next_actions: ["Оплатить диагностику"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "result":
      return {
        status_key: "result_ready",
        status_label: "Результат готов",
        status_hint: "Откройте итог",
        now_need: "Открыть результат диагностики",
        cta_key: "result",
        cta_label: "Открыть результат",
        sla_note: "Результат в кабинете.",
        required_uploaded: 2,
        required_total: 2,
        consent_ok: true,
        stages: stages(4),
        documents: baseDocs.map((d) => ({
          ...d,
          status: "accepted",
          status_label: "Принят для текущего этапа",
          added_at: "25 октября, 12:00",
          document_id: `doc-${d.key}`,
        })),
        order: { ...order, state: "paid", status_label: "Оплата получена" },
        result: { ready: true, document_id: "doc-result-1", added_at: "25 октября, 15:00" },
        next_actions: ["Открыть результат"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "unavailable":
      return {
        status_key: "result_ready",
        status_label: "Результат готов",
        status_hint: "Файл ещё готовится",
        now_need: "Открыть результат диагностики",
        cta_key: "result",
        cta_label: "Открыть результат",
        sla_note: "Файл появится после публикации.",
        required_uploaded: 2,
        required_total: 2,
        consent_ok: true,
        stages: stages(4),
        documents: baseDocs,
        order: { ...order, state: "paid", status_label: "Оплата получена" },
        result: { ready: true, document_id: null, added_at: null },
        next_actions: ["Открыть результат"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "unknown":
      return {
        status_key: "waiting_docs",
        status_label: "Ждём документы",
        status_hint: "Неизвестный шаг",
        now_need: "Неизвестное действие",
        cta_key: "mystery_future_cta",
        cta_label: "Странная кнопка",
        sla_note: "Нужно обновить страницу.",
        required_uploaded: 0,
        required_total: 2,
        consent_ok: true,
        stages: stages(2),
        documents: baseDocs.map((d) => ({
          ...d,
          status: "missing",
          added_at: null,
          document_id: null,
        })),
        order,
        result,
        next_actions: [],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
    case "upload":
    default:
      return {
        status_key: "waiting_docs",
        status_label: "Ждём документы",
        status_hint: "Нужна выписка ИЛС",
        now_need: "Загрузить Выписка ИЛС",
        cta_key: "upload",
        cta_label: "Перейти к загрузке документов",
        sla_note: "После загрузки проверим комплект.",
        required_uploaded: 1,
        required_total: 2,
        consent_ok: true,
        stages: stages(2),
        documents: baseDocs,
        order,
        result,
        next_actions: ["Загрузить: Выписка ИЛС"],
        ils_howto_url: "https://proverkastaza.ru/blog/kak-proverit-stazh-v-vypiske-ils/",
        offer_url: "https://proverkastaza.ru/oferta/",
      };
  }
}

const SCENARIOS: { id: ScenarioId; title: string }[] = [
  { id: "consent", title: "Согласие" },
  { id: "upload", title: "Загрузка ИЛС" },
  { id: "waiting", title: "Ждём специалиста" },
  { id: "reupload", title: "Нужна замена" },
  { id: "contract", title: "Договор" },
  { id: "pay", title: "Оплата" },
  { id: "result", title: "Результат" },
  { id: "unavailable", title: "CTA недоступен" },
  { id: "unknown", title: "Неизвестный CTA" },
];

function isScenarioId(value: string | null): value is ScenarioId {
  return SCENARIOS.some((row) => row.id === value);
}

export function RoutePreviewClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromQuery = searchParams.get("s");
  const scenario: ScenarioId = isScenarioId(fromQuery) ? fromQuery : "upload";
  const [log, setLog] = useState<string[]>([]);
  const [lastHandler, setLastHandler] = useState<string>("—");
  const [messageBody, setMessageBody] = useState("");
  const work = useMemo(() => workFor(scenario), [scenario]);
  const resolved = useMemo(
    () => resolveRoutePrimaryAction(work, { hasContractHandler: true }),
    [work],
  );

  const resolveLine = `resolve(${scenario}) → ${JSON.stringify(resolved)}`;
  const displayHandler = lastHandler === "—" ? resolveLine : lastHandler;

  function pushLog(line: string) {
    const stamped = `${new Date().toLocaleTimeString("ru-RU")} · ${line}`;
    setLastHandler(line);
    setLog((prev) => [stamped, ...prev].slice(0, 16));
  }

  useEffect(() => {
    const paint = () => {
      const el = document.getElementById("route-preview-viewport");
      const layout = document.querySelector(".cabinet-case-layout");
      const mode = layout?.getAttribute("data-layout") || "—";
      const chatW = layout?.getAttribute("data-chat-width") || "auto";
      if (el) {
        el.textContent = `Viewport: ${window.innerWidth}×${window.innerHeight}px · layout=${mode} · chat-width=${chatW}`;
      }
    };
    paint();
    window.addEventListener("resize", paint);
    const timer = window.setInterval(paint, 500);
    return () => {
      window.removeEventListener("resize", paint);
      window.clearInterval(timer);
    };
  }, []);

  function selectScenario(id: ScenarioId) {
    router.replace(`/dev/route-preview?s=${id}`);
    pushLog(`сценарий → ${id}`);
  }

  function invokeResolvedHandler() {
    if (resolved.kind === "consent") {
      pushLog("handler: consent");
      return;
    }
    if (resolved.kind === "contract") {
      pushLog("handler: contract");
      return;
    }
    if (resolved.kind === "pay") {
      pushLog(`handler: pay ${resolved.orderId}`);
      return;
    }
    if (resolved.kind === "result") {
      pushLog(`handler: result ${resolved.documentId}`);
      return;
    }
    if (resolved.kind === "upload") {
      pushLog(`handler: upload slot=${resolved.slotKey} (без открытия file picker в preview)`);
      return;
    }
    pushLog(`handler: skip (${JSON.stringify(resolved)})`);
  }

  return (
    <div className="app-layout app-layout--case" style={{ paddingTop: "1rem" }}>
      <header className="panel" style={{ marginBottom: "1rem" }}>
        <h1 style={{ margin: 0, fontSize: "1.2rem" }}>
          React preview: CaseRoutePanel внутри CaseWorkMap
        </h1>
        <p className="hint" style={{ margin: "0.4rem 0 0" }}>
          PR #284 · до merge · слева маршрут, справа чат · ширина чата тянется разделителем · CTA в
          журнал (не toast HTML-макета)
        </p>
        <p className="hint" id="route-preview-viewport" style={{ margin: "0.35rem 0 0" }}>
          Viewport: —
        </p>
        <div className="case-route-actions" style={{ marginTop: "0.75rem" }}>
          {SCENARIOS.map((row) => (
            <a
              key={row.id}
              className={scenario === row.id ? "button-link" : "secondary"}
              href={`/dev/route-preview?s=${row.id}`}
              onClick={(event) => {
                event.preventDefault();
                selectScenario(row.id);
              }}
            >
              {row.title}
            </a>
          ))}
        </div>
      </header>

      <CabinetCaseLayout
        main={
          <CaseWorkMap
            caseNumber="1001"
            work={work}
            warning={WARNING}
            expertAssigned={scenario !== "consent"}
            onConsent={() => pushLog("handler: consent")}
            onContract={() => pushLog("handler: contract")}
            onUpload={(file, docType) =>
              pushLog(`handler: upload file=${file.name} docType=${docType || "—"}`)
            }
            onUploadMultiple={(files, docType) =>
              pushLog(`handler: uploadMultiple n=${files.length} docType=${docType || "—"}`)
            }
            onDelete={(documentId) => pushLog(`handler: delete ${documentId}`)}
            onPay={(orderId) => pushLog(`handler: pay ${orderId}`)}
            onDownloadResult={(documentId) => pushLog(`handler: result ${documentId}`)}
          />
        }
        chat={
          <ClientCaseChatPanel
            messages={[
              {
                id: "m1",
                author_kind: "system",
                body: "Это тестовая лента preview. Сообщения не уходят в MAX.",
                created_at: "2026-10-25T10:00:00+00:00",
              },
              {
                id: "m2",
                author_kind: "staff",
                body: "Напишите сюда вопрос — поле ввода справа от маршрута.",
                created_at: "2026-10-25T10:05:00+00:00",
              },
              {
                id: "m3",
                author_kind: "client",
                body: "Длинная история для проверки прокрутки внутри панели чата. Сообщение 3.",
                created_at: "2026-10-25T10:06:00+00:00",
              },
              {
                id: "m4",
                author_kind: "staff",
                body: "Сообщение 4 — лента длиннее окна, поле ввода остаётся снизу.",
                created_at: "2026-10-25T10:07:00+00:00",
              },
              {
                id: "m5",
                author_kind: "client",
                body: "Сообщение 5.",
                created_at: "2026-10-25T10:08:00+00:00",
              },
              {
                id: "m6",
                author_kind: "staff",
                body: "Сообщение 6.",
                created_at: "2026-10-25T10:09:00+00:00",
              },
              {
                id: "m7",
                author_kind: "client",
                body: "Сообщение 7.",
                created_at: "2026-10-25T10:10:00+00:00",
              },
              {
                id: "m8",
                author_kind: "staff",
                body: "Сообщение 8 — конец ленты preview.",
                created_at: "2026-10-25T10:11:00+00:00",
              },
            ]}
            body={messageBody}
            busy={false}
            maxHref="https://max.ru/"
            onBodyChange={setMessageBody}
            onSend={(event, text) => {
              event.preventDefault();
              pushLog(`handler: chat send «${text.slice(0, 40)}»`);
              setMessageBody("");
            }}
          />
        }
      />
      <a className="case-chat-mobile-open" href="#case-chat">
        Чат
      </a>

      <aside className="panel" style={{ marginTop: "1rem" }} aria-live="polite" id="route-preview-handler-log">
        <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Журнал обработчиков</h2>
        <p className="hint" style={{ marginTop: 0 }}>
          Текущий resolve: <code>{JSON.stringify(resolved)}</code>
        </p>
        <p>
          Последний handler: <strong data-testid="last-handler">{displayHandler}</strong>
        </p>
        <div className="case-route-actions" style={{ marginBottom: "0.75rem" }}>
          <button type="button" onClick={invokeResolvedHandler}>
            Вызвать handler сценария
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setLog([]);
              setLastHandler("—");
            }}
          >
            Очистить журнал
          </button>
        </div>
        {log.length === 0 ? (
          <p className="hint">Нажмите основную кнопку маршрута, «Вызвать handler» или отправьте сообщение в чат.</p>
        ) : (
          <ul className="plain-list">
            {log.map((line, index) => (
              <li key={`${index}-${line}`}>{line}</li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
