/** CSV периодов ИЛС / трудовой для скачивания и загрузки исправленного. */

export type PeriodRow = Record<string, unknown>;

const HEADERS = ["source", "period_id", "start", "end", "label", "raw_json"] as const;

function cell(v: unknown): string {
  const s = v == null ? "" : String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function periodsToCsv(ils: PeriodRow[], labor: PeriodRow[]): string {
  const lines = [HEADERS.join(",")];
  for (const [source, rows] of [
    ["ils", ils],
    ["labor", labor],
  ] as const) {
    for (const row of rows) {
      const start = row.start ?? row.start_date ?? row.from ?? "";
      const end = row.end ?? row.end_date ?? row.to ?? "";
      const label = row.label ?? row.title ?? row.employer ?? row.name ?? "";
      const periodId = row.period_id ?? row.id ?? "";
      lines.push(
        [
          source,
          cell(periodId),
          cell(start),
          cell(end),
          cell(label),
          cell(JSON.stringify(row)),
        ].join(","),
      );
    }
  }
  return `${lines.join("\n")}\n`;
}

export function downloadTextFile(filename: string, text: string, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Парсит CSV обратно в ils/labor (берёт raw_json, если есть). */
export function parsePeriodsCsv(text: string): { ils: PeriodRow[]; labor: PeriodRow[] } {
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return { ils: [], labor: [] };
  const ils: PeriodRow[] = [];
  const labor: PeriodRow[] = [];
  for (const line of lines.slice(1)) {
    const cols = splitCsvLine(line);
    if (cols.length < 2) continue;
    const source = (cols[0] || "").trim().toLowerCase();
    let row: PeriodRow;
    const raw = cols[5] || "";
    if (raw.trim().startsWith("{")) {
      try {
        row = JSON.parse(raw) as PeriodRow;
      } catch {
        row = {
          period_id: cols[1],
          start: cols[2],
          end: cols[3],
          label: cols[4],
        };
      }
    } else {
      row = {
        period_id: cols[1],
        start: cols[2],
        end: cols[3],
        label: cols[4],
      };
    }
    if (source === "labor") labor.push(row);
    else ils.push(row);
  }
  return { ils, labor };
}

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (ch === '"') {
        inQ = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQ = true;
    } else if (ch === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}
