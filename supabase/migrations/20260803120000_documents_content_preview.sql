-- Краткое содержание документа для клиента после загрузки
alter table public.documents
  add column if not exists content_preview text;

comment on column public.documents.content_preview is
  'Укороченный фрагмент распознанного текста для UI клиента (без полного OCR).';
