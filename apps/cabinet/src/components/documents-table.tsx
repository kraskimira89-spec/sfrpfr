"use client";

import { useMemo, useState } from "react";

export type CabinetDocument = {
  id: string;
  storage_path: string;
  doc_type?: string | null;
  doc_type_label?: string | null;
  created_at?: string;
  filename?: string | null;
  content_preview?: string | null;
  inner_date?: string | null;
  inner_title?: string | null;
  document_group_id?: string | null;
  page_index?: number | null;
  page_order?: number | null;
  upload_batch_id?: string | null;
  ingest_status?: string | null;
  progress_percent?: number | null;
  progress_message?: string | null;
  placement_suggestion?: Record<string, unknown> | null;
  requirement_code?: string | null;
  client_declared_signed?: boolean;
  antivirus_status?: string | null;
  ingest_review_required?: boolean;
  ingest_artifact_path?: string | null;
  downloadable?: boolean;
};

type SortKey = "created_at" | "filename" | "inner_date" | "inner_title";
type SortDir = "asc" | "desc";

type Props = {
  documents: CabinetDocument[];
  onOpen: (documentId: string) => void;
  busy?: boolean;
  emptyHint?: string;
  selectedIds?: string[];
  onToggleSelect?: (documentId: string) => void;
  onToggleAll?: (checked: boolean) => void;
  onBulkDownload?: () => void;
};

function formatUploadAt(value?: string) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function uniqueValues(rows: CabinetDocument[], key: SortKey): string[] {
  const set = new Set<string>();
  for (const row of rows) {
    if (key === "created_at") {
      set.add(formatUploadAt(row.created_at));
    } else if (key === "filename") {
      set.add((row.filename || row.storage_path.split("/").pop() || "документ").trim());
    } else if (key === "inner_date") {
      set.add((row.inner_date || "—").trim());
    } else {
      set.add((row.inner_title || row.doc_type_label || "Документ").trim());
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b, "ru"));
}

function cellValue(row: CabinetDocument, key: SortKey): string {
  if (key === "created_at") return formatUploadAt(row.created_at);
  if (key === "filename") {
    return (row.filename || row.storage_path.split("/").pop() || "документ").trim();
  }
  if (key === "inner_date") return (row.inner_date || "—").trim();
  return (row.inner_title || row.doc_type_label || "Документ").trim();
}

function sortValue(row: CabinetDocument, key: SortKey): string | number {
  if (key === "created_at") {
    const t = row.created_at ? Date.parse(row.created_at) : 0;
    return Number.isNaN(t) ? 0 : t;
  }
  if (key === "inner_date") {
    const raw = (row.inner_date || "").trim();
    const m = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (m) return Number(`${m[3]}${m[2]}${m[1]}`);
    return raw;
  }
  return cellValue(row, key).toLowerCase();
}

export function DocumentsTable({
  documents,
  onOpen,
  busy,
  emptyHint = "Пока файлов нет — загрузите выписку ИЛС или трудовую книжку.",
  selectedIds = [],
  onToggleSelect,
  onToggleAll,
  onBulkDownload,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("inner_date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [filters, setFilters] = useState<Record<SortKey, string>>({
    created_at: "",
    filename: "",
    inner_date: "",
    inner_title: "",
  });

  const filtered = useMemo(() => {
    return documents.filter((row) =>
      (Object.keys(filters) as SortKey[]).every((key) => {
        const selected = filters[key];
        if (!selected) return true;
        return cellValue(row, key) === selected;
      }),
    );
  }, [documents, filters]);

  const sorted = useMemo(() => {
    const rows = [...filtered];
    rows.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      let cmp = 0;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv), "ru");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [filtered, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir(key === "created_at" || key === "inner_date" ? "desc" : "asc");
  }

  function sortMark(key: SortKey) {
    if (sortKey !== key) return "↕";
    return sortDir === "asc" ? "↑" : "↓";
  }

  const columns: { key: SortKey; label: string }[] = [
    { key: "inner_date", label: "Дата документа" },
    { key: "inner_title", label: "Название документа" },
    { key: "created_at", label: "Дата загрузки" },
    { key: "filename", label: "Файл" },
  ];

  function statusLabel(doc: CabinetDocument): string {
    if (doc.progress_message) return doc.progress_message;
    if (doc.ingest_status === "under_review") return "Файл получен — специалист проверит";
    if (doc.ingest_status === "needs_reupload") return "Нужна повторная загрузка";
    return doc.ingest_status || "—";
  }

  const selectable = documents.filter((d) => d.downloadable !== false);
  const allSelected =
    selectable.length > 0 && selectable.every((d) => selectedIds.includes(d.id));

  return (
    <div className="docs-table-wrap" id="docs-table">
      <div className="docs-table-head">
        <h2>Загруженные документы</h2>
        <p className="docs-count">
          Всего: {documents.length}
          {filtered.length !== documents.length ? ` · показано: ${filtered.length}` : ""}
        </p>
        {onBulkDownload ? (
          <p className="home-actions">
            <button
              type="button"
              disabled={busy || selectedIds.length === 0}
              onClick={onBulkDownload}
            >
              Скачать выбранные ({selectedIds.length})
            </button>
          </p>
        ) : null}
      </div>
      <div className="docs-table-scroll">
        <table className="docs-table">
          <thead>
            <tr>
              {onToggleSelect ? (
                <th scope="col">
                  <input
                    type="checkbox"
                    aria-label="Выбрать все на странице"
                    checked={allSelected}
                    disabled={busy || selectable.length === 0}
                    onChange={(e) => onToggleAll?.(e.target.checked)}
                  />
                </th>
              ) : null}
              <th scope="col" className="docs-table-num">
                №
              </th>
              {columns.map((col) => (
                <th scope="col" key={col.key}>
                  <button
                    type="button"
                    className="docs-sort-btn"
                    onClick={() => toggleSort(col.key)}
                    aria-label={`Сортировать: ${col.label}`}
                  >
                    {col.label} <span aria-hidden="true">{sortMark(col.key)}</span>
                  </button>
                  <label className="docs-filter">
                    <span className="sr-only">Фильтр: {col.label}</span>
                    <select
                      value={filters[col.key]}
                      disabled={busy}
                      onChange={(e) =>
                        setFilters((prev) => ({ ...prev, [col.key]: e.target.value }))
                      }
                    >
                      <option value="">Все</option>
                      {uniqueValues(documents, col.key).map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                </th>
              ))}
              <th scope="col">Статус</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((doc, index) => (
              <tr key={doc.id}>
                {onToggleSelect ? (
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Выбрать ${cellValue(doc, "filename")}`}
                      checked={selectedIds.includes(doc.id)}
                      disabled={busy || doc.downloadable === false}
                      onChange={() => onToggleSelect(doc.id)}
                    />
                  </td>
                ) : null}
                <td className="docs-table-num">{index + 1}</td>
                {columns.map((col) => (
                  <td key={col.key}>
                    {col.key === "filename" ? (
                      <button
                        type="button"
                        className="linkish"
                        title="Скачать файл"
                        aria-label={`Скачать файл: ${cellValue(doc, "filename")}`}
                        onClick={() => onOpen(doc.id)}
                      >
                        {cellValue(doc, "filename")}
                      </button>
                    ) : (
                      cellValue(doc, col.key)
                    )}
                  </td>
                ))}
                <td className="hint">{statusLabel(doc)}</td>
              </tr>
            ))}
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={onToggleSelect ? 7 : 6} className="hint">
                  {documents.length === 0 ? emptyHint : "Нет строк по выбранным фильтрам."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
