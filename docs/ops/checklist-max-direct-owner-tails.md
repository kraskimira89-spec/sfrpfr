# Ops: хвосты MAX + Директ (владелец)

**Дата:** 2026-08-23

## MAX — описание канала

Текст канона: [`scripts/assets/max-channel/channel-description.md`](../../scripts/assets/max-channel/channel-description.md)  
Вставить **вручную** в UI настроек канала (лимит ≤399).

## MAX — очередь постов 08+

Посты в [`starter-posts.json`](../../scripts/assets/max-channel/starter-posts.json): `08-ils` … `18-invite`.  
Публикация только через премодерацию (личка ops → **Опубликовать**). Автопакет `--direct` запрещён.

```powershell
.\.venv\Scripts\Activate.ps1
# по одному, например:
sfrfr max-channel-publish-starter --only 08-ils
# далее 09-sverka … 18-invite — после Approve в ops
```

Календарь: [`plan-2026-08-17.json`](../../scripts/assets/max-channel/plan-2026-08-17.json).

## Директ

План: [`research-test-noyabrsk-north-direct-2026-08.md`](../marketing-sales/research-test-noyabrsk-north-direct-2026-08.md)  
**Статус: BLOCKED до бюджета владельца.** Кампании не запускать из агента.
