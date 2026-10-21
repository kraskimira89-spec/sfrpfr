/** Группировка exact checksum: одинаковые байты → одна строка + история повторов. */

export type DedupeDoc = {
  id: string;
  storage_path?: string;
  filename?: string | null;
  created_at?: string;
  checksum_sha256?: string | null;
};

export type DocumentChecksumGroup<T extends DedupeDoc> = {
  /** Самый свежий экземпляр (по created_at). */
  primary: T;
  /** Более ранние / прочие с тем же checksum (не по имени файла). */
  duplicates: T[];
};

function checksumKey(doc: DedupeDoc): string | null {
  const cs = (doc.checksum_sha256 || "").trim();
  return cs || null;
}

function sortNewestFirst<T extends DedupeDoc>(rows: T[]): T[] {
  return [...rows].sort((a, b) => {
    const at = a.created_at ? Date.parse(a.created_at) : 0;
    const bt = b.created_at ? Date.parse(b.created_at) : 0;
    return (Number.isNaN(bt) ? 0 : bt) - (Number.isNaN(at) ? 0 : at);
  });
}

/**
 * Exact checksum → группа. Разные байты (даже одно имя) — разные группы.
 * Без checksum — каждый id отдельно (не сливать по имени).
 */
export function groupCabinetDocumentsByChecksum<T extends DedupeDoc>(
  documents: T[],
): DocumentChecksumGroup<T>[] {
  const byChecksum = new Map<string, T[]>();
  const singles: T[] = [];

  for (const doc of documents) {
    const key = checksumKey(doc);
    if (!key) {
      singles.push(doc);
      continue;
    }
    const bucket = byChecksum.get(key);
    if (bucket) bucket.push(doc);
    else byChecksum.set(key, [doc]);
  }

  const groups: DocumentChecksumGroup<T>[] = [];
  for (const rows of byChecksum.values()) {
    const ordered = sortNewestFirst(rows);
    groups.push({ primary: ordered[0]!, duplicates: ordered.slice(1) });
  }
  for (const doc of singles) {
    groups.push({ primary: doc, duplicates: [] });
  }

  return sortNewestFirst(groups.map((g) => g.primary)).map((primary) => {
    const found = groups.find((g) => g.primary.id === primary.id);
    return found ?? { primary, duplicates: [] };
  });
}

/** Устаревший helper: только primary без истории (для простых списков). */
export function dedupeCabinetDocuments<T extends DedupeDoc>(documents: T[]): T[] {
  return groupCabinetDocumentsByChecksum(documents).map((g) => g.primary);
}
