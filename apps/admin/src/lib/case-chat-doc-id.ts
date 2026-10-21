/** Связь журнала с documents.id — открывать только по id, не по имени файла. */
export const DOC_ID_RE =
  /\s·\sdoc_id=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b/i;

/** Вытащить document_id из тела события [Документ]; doc_id может быть не в конце строки. */
export function extractCaseChatDocumentId(body: string): {
  documentId: string | null;
  textWithoutDocId: string;
} {
  const text = body ?? "";
  const match = text.match(DOC_ID_RE);
  if (!match) {
    return { documentId: null, textWithoutDocId: text };
  }
  return {
    documentId: match[1] || null,
    textWithoutDocId: text.replace(DOC_ID_RE, "").trimEnd(),
  };
}
