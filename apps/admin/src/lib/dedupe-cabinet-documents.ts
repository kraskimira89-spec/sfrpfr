/** Один логический файл: checksum (одинаковые байты) или id. */

export type DedupeDoc = {
  id: string;
  storage_path?: string;
  filename?: string | null;
  created_at?: string;
  checksum_sha256?: string | null;
};

export function dedupeCabinetDocuments<T extends DedupeDoc>(documents: T[]): T[] {
  const seen = new Set<string>();
  const ordered = [...documents].sort((a, b) => {
    const at = a.created_at ? Date.parse(a.created_at) : 0;
    const bt = b.created_at ? Date.parse(b.created_at) : 0;
    return (Number.isNaN(bt) ? 0 : bt) - (Number.isNaN(at) ? 0 : at);
  });
  const out: T[] = [];
  for (const doc of ordered) {
    const key =
      (doc.checksum_sha256 || "").trim() ||
      (doc.id || "").trim() ||
      `path:${doc.storage_path || doc.filename || ""}`;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(doc);
  }
  return out;
}
