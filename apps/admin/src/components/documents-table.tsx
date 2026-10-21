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
  downloadable?: boolean | null;
  ingest_status?: string | null;
};

type SortKey = "created_at" | "filename" | "inner_date" | "inner_title";
type SortDir = "asc" | "desc";

type Props = {
  documents: CabinetDocument[];
  onOpen: (documentId: string) => void;
  busy?: boolean;
  emptyHint?: string;
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
  emptyHint = "Пока файлов нет — клиент ещё не загрузил документы.",
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
    { key: "inner_title", label: "Тип / название" },
    { key: "created_at", label: "Загружен" },
    { key: "filename", label: "Файл" },
  ];

  return (
    <div className="docs-table-wrap" id="docs-table">
      <div className="docs-table-head">
        <h2>Документы в деле</h2>
        <p className="docs-count">
          Всего: {documents.length}
          {filtered.length !== documents.length ? ` · показано: ${filtered.length}` : ""}
          {" · "}
          откройте файл кнопкой «Открыть» — кабинет сотрудника достаточно
        </p>
      </div>
      <div className="docs-table-scroll">
        <table className="docs-table">
          <thead>
            <tr>
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
              <th scope="col">Действие</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((doc, index) => {
              const typeLabel =
                (doc.doc_type_label || doc.inner_title || "Документ").trim() || "Документ";
              const preview = (doc.content_preview || "").trim();
              const canOpen = doc.downloadable !== false;
              return (
                <tr key={doc.id}>
                  <td className="docs-table-num">{index + 1}</td>
                  <td>
                    <div>{typeLabel}</div>
                    {preview ? (
                      <p className="hint" style={{ margin: "0.25rem 0 0", maxWidth: "28rem" }}>
                        {preview.length > 160 ? `${preview.slice(0, 160)}…` : preview}
                      </p>
                    ) : null}
                  </td>
                  <td>{cellValue(doc, "created_at")}</td>
                  <td>{cellValue(doc, "filename")}</td>
                  <td>
                    <button
                      type="button"
                      className="linkish"
                      disabled={busy || !canOpen}
                      title={canOpen ? "Открыть в новой вкладке" : "Файл ещё недоступен"}
                      aria-label={`Открыть: ${cellValue(doc, "filename")}`}
                      onClick={() => onOpen(doc.id)}
                    >
                      Открыть
                    </button>
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={5} className="hint">
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
