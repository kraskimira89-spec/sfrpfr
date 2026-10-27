/** Итог «как было / как стало» + хронология документов: кратко в чат, полно в файл. */

export type ResultSummaryDoc = {
  id?: string;
  storage_path?: string;
  filename?: string | null;
  doc_type?: string | null;
  doc_type_label?: string | null;
  created_at?: string | null;
  inner_date?: string | null;
  inner_title?: string | null;
};

export type ResultSummaryInput = {
  beforeRub?: string | number | null;
  afterRub?: string | number | null;
  lumpRub?: string | number | null;
  documents?: ResultSummaryDoc[] | null;
  caseRef?: string | null;
};

function money(v: string | number | null | undefined): string {
  const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/\s/g, "").replace(",", "."));
  if (!Number.isFinite(n) || n < 0) return "—";
  return `${Math.round(n).toLocaleString("ru-RU")} ₽`;
}

function docName(d: ResultSummaryDoc): string {
  const fromPath = (d.storage_path || "").split("/").pop() || "";
  return (
    (d.inner_title || "").trim() ||
    (d.filename || "").trim() ||
    fromPath ||
    (d.doc_type_label || "").trim() ||
    (d.doc_type || "").trim() ||
    "документ"
  );
}

function docWhen(d: ResultSummaryDoc): string {
  const raw = d.inner_date || d.created_at || "";
  if (!raw) return "дата не указана";
  const t = Date.parse(raw);
  if (Number.isNaN(t)) return String(raw).slice(0, 16);
  return new Date(t).toLocaleDateString("ru-RU");
}

export function sortDocsChronology(docs: ResultSummaryDoc[]): ResultSummaryDoc[] {
  return [...docs].sort((a, b) => {
    const ta = Date.parse(a.inner_date || a.created_at || "") || 0;
    const tb = Date.parse(b.inner_date || b.created_at || "") || 0;
    return ta - tb;
  });
}

/** Краткая выгрузка в чат клиенту (без ПДн). */
export function formatResultSummaryBrief(input: ResultSummaryInput): string {
  const before = money(input.beforeRub);
  const after = money(input.afterRub);
  const lump = money(input.lumpRub);
  const docs = sortDocsChronology(input.documents ?? []);
  const docsLine =
    docs.length === 0
      ? "Документы в деле: пока без списка в этой выгрузке."
      : `В деле документов: ${docs.length} (полная хронология — в файле у специалиста).`;

  const delta =
    before !== "—" && after !== "—"
      ? (() => {
          const b = Number(String(input.beforeRub).replace(/\s/g, "").replace(",", "."));
          const a = Number(String(input.afterRub).replace(/\s/g, "").replace(",", "."));
          if (!Number.isFinite(b) || !Number.isFinite(a)) return "";
          const d = Math.round(a - b);
          if (d === 0) return " Изменение ежемесячной суммы: без изменения.";
          const sign = d > 0 ? "+" : "";
          return ` Изменение ежемесячной: ${sign}${d.toLocaleString("ru-RU")} ₽.`;
        })()
      : "";

  return (
    `Здравствуйте! Краткий итог по ответу СФР (подведение итогов):\n` +
    `• Как было: ${before}\n` +
    `• Как стало: ${after}\n` +
    (lump !== "—" && lump !== "0 ₽" ? `• Единовременно: ${lump}\n` : "") +
    `${delta ? `•${delta.trim()}\n` : ""}` +
    `• ${docsLine}`
  );
}

/** Полная выгрузка в файл для сотрудника. */
export function formatResultSummaryFull(input: ResultSummaryInput): string {
  const before = money(input.beforeRub);
  const after = money(input.afterRub);
  const lump = money(input.lumpRub);
  const docs = sortDocsChronology(input.documents ?? []);
  const ref = (input.caseRef || "").trim() || "—";
  const lines: string[] = [
    "Итог по делу (полная выгрузка)",
    `Служебный ref: ${ref}`,
    `Дата выгрузки: ${new Date().toLocaleString("ru-RU")}`,
    "",
    "Как было / как стало",
    `  Прежний размер: ${before}`,
    `  Новый размер: ${after}`,
    `  Единовременно: ${lump}`,
    "",
    `Хронология документов (${docs.length})`,
  ];
  if (docs.length === 0) {
    lines.push("  (пусто)");
  } else {
    docs.forEach((d, i) => {
      const kind = (d.doc_type_label || d.doc_type || "файл").toString();
      lines.push(`  ${i + 1}. ${docWhen(d)} — ${docName(d)} [${kind}]`);
    });
  }
  lines.push(
    "",
    "Позиция сервиса: готовим документы и план; подачу через СФР/Госуслуги выполняет клиент; решение принимает СФР.",
    "",
  );
  return lines.join("\n");
}
