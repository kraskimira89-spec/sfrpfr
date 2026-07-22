# Деплой: WordPress + API на VPS (reg.ru)

## Топология

```text
домен (reg.ru DNS)
├── example.ru          → WordPress (лендинг, блог, формы)
└── api.example.ru      → FastAPI SFRFR (uvicorn/gunicorn + nginx)
                              │
                              ├─ HTTPS webhook MAX
                              │    POST /api/integrations/max/webhook
                              └─ LLM → Yandex AI Studio
```

WordPress — витрина и контент. Бизнес-логика кейсов, OCR, AI и бот MAX — на API-поддомене.

## DNS (reg.ru)

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | IP VPS |
| A | `api` | IP VPS (тот же или отдельный) |
| A | `www` | IP VPS (опционально) |

SSL: Let's Encrypt (certbot) на оба хоста. Для MAX webhook нужен **валидный HTTPS**.

## Nginx (эскиз)

```nginx
# api.example.ru
server {
    listen 443 ssl http2;
    server_name api.example.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

WordPress — отдельный `server_name example.ru` на php-fpm (как обычно).

## Env на VPS

В `.env` API:

```env
PUBLIC_BASE_URL=https://api.example.ru
AI_PROVIDER=yandex
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
MAX_BOT_TOKEN=...
MAX_WEBHOOK_SECRET=...
```

Подписка webhook MAX:

```powershell
sfrfr max-subscribe
# или вручную URL: https://api.example.ru/api/integrations/max/webhook
```

## Связка с WordPress

- На лендинге — кнопка «Написать в MAX» (deep link на бота).
- Формы WP не принимают ПДн-сканы в MVP; загрузка документов — через MAX или кабинет на `api`.
- При необходимости WP → API через серверный ключ (не публиковать service role в JS).
