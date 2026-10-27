/** Входящие ответы на ступени 11: СФР и другие органы. */

export type IncomingResponseDoc = {
  id: string;
  filename?: string | null;
  storage_path?: string | null;
  doc_type?: string | null;
  created_at?: string | null;
  inner_date?: string | null;
};

const MARKERS = [
  "sfr_decision",
  "sfr_response",
  "sfr_refusal",
  "agency_response",
] as const;

export function isIncomingResponseDoc(d: {
  doc_type?: string | null;
  storage_path?: string | null;
}): boolean {
  const blob = `${d.doc_type || ""} ${d.storage_path || ""}`.toLowerCase();
  return MARKERS.some((m) => blob.includes(m));
}

export function incomingDocLabel(d: IncomingResponseDoc): string {
  const fromPath = (d.storage_path || "").split("/").pop() || "";
  return (d.filename || "").trim() || fromPath || d.doc_type || d.id.slice(0, 8);
}

export function filterIncomingResponseDocs<T extends IncomingResponseDoc>(
  docs: T[] | null | undefined,
): T[] {
  return (docs || []).filter(isIncomingResponseDoc);
}
