"use client";

import { useEffect, useState } from "react";

type Category = { code: string; label: string };

type MailHint = {
  inbox?: string;
  compose?: { mailto?: string; subject?: string; to?: string };
  categories?: Category[];
  hint?: string;
};

const FALLBACK_CATEGORIES: Category[] = [
  { code: "children", label: "Дети (свидетельство и др.)" },
  { code: "stazh", label: "Стаж / архивная справка" },
  { code: "guardianship", label: "Опекунство" },
  { code: "contract", label: "Договор" },
  { code: "other", label: "Другое" },
  { code: "unknown", label: "Не знаю — уточнит специалист" },
];

export function AddExtraDocumentPanel({
  caseId,
  token,
  apiBase,
  busy,
  onUpload,
  onNotice,
}: {
  caseId: string;
  token: string;
  apiBase: string;
  busy?: boolean;
  onUpload: (files: File[], category: string) => Promise<string | null | void>;
  onNotice: (msg: string) => void;
}) {
  const [category, setCategory] = useState("unknown");
  const [categories, setCategories] = useState<Category[]>(FALLBACK_CATEGORIES);
  const [mail, setMail] = useState<MailHint | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => {
      void (async () => {
        try {
          const res = await fetch(
            `${apiBase}/api/portal/cases/${caseId}/document-mail-hint`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (!res.ok) return;
          const data = (await res.json()) as MailHint;
          setMail(data);
          if (data.categories?.length) setCategories(data.categories);
        } catch {
          /* ignore */
        }
      })();
    }, 0);
    return () => window.clearTimeout(t);
  }, [apiBase, caseId, token]);

  return (
    <section className="card" style={{ marginTop: "1rem" }} id="add-extra-document">
      <h3 style={{ marginTop: 0 }}>Добавить документ</h3>
      <p className="hint">
        Можно прислать свидетельство о рождении, справку о стаже, документ об опекунстве, договор
        или другой материал на любом этапе — возвращаться к сбору комплекта не нужно. Категорию
        можно не выбирать.
      </p>
      <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
        <select
          value={category}
          disabled={busy || uploading}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Категория документа"
        >
          {categories.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>
        <label className="secondary" style={{ cursor: busy ? "wait" : "pointer" }}>
          Выбрать файлы…
          <input
            type="file"
            multiple
            hidden
            disabled={busy || uploading}
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              e.target.value = "";
              if (!files.length) return;
              setUploading(true);
              void (async () => {
                try {
                  const msg = await onUpload(files, category);
                  onNotice(
                    msg ||
                      "Документ получен и добавлен в дело. Специалист проверит его и сообщит, нужны ли уточнения. Повторно отправлять файл не нужно.",
                  );
                } catch (err) {
                  onNotice(
                    err instanceof Error
                      ? err.message
                      : "Файл не сохранён. Исправьте проблему и загрузите снова.",
                  );
                } finally {
                  setUploading(false);
                }
              })();
            }}
          />
        </label>
        {mail?.compose?.mailto ? (
          <a className="button-link" href={mail.compose.mailto}>
            Отправить документы по почте
          </a>
        ) : null}
      </div>
      {mail?.inbox ? (
        <p className="hint" style={{ marginTop: "0.5rem" }}>
          Служебный адрес: <strong>{mail.inbox}</strong>
          {mail.compose?.subject ? (
            <>
              <br />
              В теме письма должен остаться код SFRFR-DOC — без него письмо не попадёт в дело
              автоматически.
            </>
          ) : null}
        </p>
      ) : null}
    </section>
  );
}
