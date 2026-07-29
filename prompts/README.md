# Системные промпты (Cursor)

Папка с **готовыми системными промптами** для узких агентов в чате Cursor.

## Как использовать

1. Откройте новый чат Agent в Cursor.
2. Вставьте содержимое нужного файла из `prompts/system/` в начало сообщения  
   **или** прикрепите файл через `@prompts/system/…`.
3. Дальше пишите задачу обычным языком.

Не путать с `.cursor/rules/` — правила там могут включаться автоматически;  
промпты здесь — **по запросу**, когда нужен специализированный агент.

## Каталог

| Файл | Агент | Когда брать |
|---|---|---|
| `system/yandex-cloud-agent.md` | Яндекс.Облако | Инфра YC, self-host Supabase, Object Storage, SmartCaptcha, `yc` CLI |
| `system/yandex-ai-studio-agent.md` | Yandex AI Studio | LLM/YandexGPT, `LLMClient`, промпты, embeddings, ПДн в модели |

## Готовые задания

| Файл | Результат |
|---|---|
| `tasks/yandex-cloud-terraform-staging.md` | Terraform-пример staging под folder SFRFR без `apply` и изменения prod |
| `tasks/management-analytics-russian-bi-pilot.md` | Пилоты DataLens / amoCRM / admin для выбора российского BI |

Запуск:

```text
@prompts/system/yandex-cloud-agent.md
@prompts/tasks/yandex-cloud-terraform-staging.md
```
