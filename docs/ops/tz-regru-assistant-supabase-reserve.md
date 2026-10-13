# ТЗ для ассистента reg.ru: резервный Supabase

Дата: 2026-10-13

## Техническое задание для ассистента reg.ru

### Цель
Заказать/подготовить облачный сервер в РФ и развернуть на нём **рабочий резервный self-hosted Supabase** — живой стек (Postgres + Auth + Storage + Kong/Caddy и пр.), **наравне** с прежней Яндекс-ВМ, а не «просто положить файл бэкапа». После готовности стека владелец/агент Cursor зальёт дамп и при необходимости переключит DNS `supabase.proverkastaza.ru` на новый IP.

### Контекст и исходные данные

**Почему нужен резерв**
- Основная БД была на ВМ Yandex Cloud `sfrfr-supabase-db-01`, публичный IP `51.250.69.237`, зона `ru-central1-a`.
- Дата-центр зоны остановлен после атаки БПЛА; нужен рабочий аналог стека вне этой зоны.
- Публичный домен стека: `supabase.proverkastaza.ru` (DNS зоны `proverkastaza.ru` уже у reg.ru).
- Прод-приложение (API/сайт/кабинеты) уже на VPS reg.ru: `91.229.11.147` — **этот сервер не трогать** без явного согласия владельца.

**Канон стека (как на Яндекс-ВМ)**
- Каталог: `/opt/sfrfr-supabase/supabase/docker`
- Compose: `docker-compose.yml` + override `docker-compose.sfrfr-direct-pg.yml` (прямой Postgres на хосте `:5433` → контейнер `:5432`)
- TLS: Caddy overlay `docker-compose.caddy.yml`, `PROXY_DOMAIN=supabase.proverkastaza.ru`
- UFW / firewall снаружи: **только** TCP `22`, `80`, `443`
- Postgres `5432` / `5433` и Studio `:8000` **не** публиковать в интернет

**Дамп данных**
- Логический дамп есть у владельца на ПК: `D:\SFRFR-backups\` (снимок ~11.10, 03:30 МСК).
- Ассистент reg.ru **не имеет** доступа к этому пути. После выдачи сервера и SSH дамп **передаст владелец или агент Cursor**. До передачи — поднять пустой стек healthy; restore — отдельным согласованным шагом.

**Секреты**
- `JWT_SECRET`, `POSTGRES_PASSWORD`, `ANON_KEY`, `SERVICE_ROLE_KEY` и прочие значения **не вставлять в чат**.
- Источник для владельца/агента Cursor: `secrets/supabase-staging.env`. Ассистент готовит файлы/права; значения впишет владелец/агент Cursor по SSH.

**SSH-ключ (обязательно прописать на сервер)**
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm user.kraskimira89@gmail.com
```

**DNS**
- TTL A `supabase` уже просили снизить до **300**.
- Смену A `supabase` → новый IP делает **владелец** только после того, как на новом сервере слушают 80/443.

### Параметры сервера

| Параметр | Требование |
|----------|------------|
| ОС | Ubuntu **22.04** или **24.04** LTS |
| CPU / RAM | минимум **2 vCPU / 4 ГБ**; предпочтительно **4 vCPU / 8 ГБ** |
| Диск | **≥ 40 ГБ** SSD |
| Регион | **РФ** |
| Сеть | публичный **IPv4** |
| Доступ | SSH по ключу выше |
| Firewall | inbound TCP **22, 80, 443**; **не** открывать 5432/5433/8000 |

Имя (рекомендация): `sfrfr-supabase-db-regru`.

### Разделение ролей

**Делает ассистент reg.ru**
1. Заказ/выдача сервера.
2. Docker Engine + Compose plugin.
3. `/opt/sfrfr-supabase`, clone `supabase/docker`, override `docker-compose.sfrfr-direct-pg.yml`.
4. UFW: 22/80/443.
5. Каркас `.env` (плейсхолдеры), `chmod 600`.
6. `docker compose pull` + `up -d`, проверки.
7. Каталог `/srv/supabase-data/restore/` для дампа.

**Не делает (владелец / агент Cursor)**
- Передача и `pg_restore` дампа.
- Вставка реальных секретов из `secrets/supabase-staging.env`.
- Смена DNS A `supabase`.
- Правка `.env` на прод-VPS `91.229.11.147`.
- Cutover приложения / smoke OTP.

### Шаги установки

#### 1) Сервер и SSH
Создать ВМ, привязать IPv4, прописать SSH-ключ. Вернуть: IP, логин, ОС, тариф.

#### 2) Базовое ПО
```bash
sudo apt update && sudo apt install -y git curl ca-certificates ufw
# Docker Engine + Compose plugin по docs.docker.com для Ubuntu
docker --version
docker compose version
```

#### 3) Каталог стека
```bash
sudo mkdir -p /opt/sfrfr-supabase
sudo chown -R "$USER:$USER" /opt/sfrfr-supabase
cd /opt/sfrfr-supabase
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
chmod 600 .env
```

Override:
```yaml
# docker-compose.sfrfr-direct-pg.yml
services:
  db:
    ports:
      - "5433:5432"
```

В `.env` / вызовах всегда включать override. Заполнить URL-поля:
- `API_EXTERNAL_URL=https://supabase.proverkastaza.ru`
- `SUPABASE_PUBLIC_URL=https://supabase.proverkastaza.ru`
- `PROXY_DOMAIN=supabase.proverkastaza.ru`
- `CERTBOT_EMAIL=ops@proverkastaza.ru`

Секреты (`POSTGRES_PASSWORD`, `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY`) — плейсхолдеры до владельца.

#### 4) UFW
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```
Нет allow на 5432/5433/8000 извне.

#### 5) Запуск (после секретов от владельца или временных ключей только для проверки контейнеров)
```bash
cd /opt/sfrfr-supabase/supabase/docker
docker compose pull
docker compose -f docker-compose.yml -f docker-compose.sfrfr-direct-pg.yml up -d
docker compose ps
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health
sudo ss -tlnp | grep -E ':443|:80|:5432|:5433|:8000'
```

#### 6) TLS (Caddy)
До DNS — проверка по IP возможна с ошибкой сертификата. После смены A владельцем:
```bash
docker compose -f docker-compose.yml -f docker-compose.sfrfr-direct-pg.yml -f docker-compose.caddy.yml up -d
curl -I https://supabase.proverkastaza.ru
```
Ожидание: **401** на корне (TLS + Kong/Caddy живы).

#### 7) Приём дампа (без restore)
```bash
sudo mkdir -p /srv/supabase-data/restore
sudo chown -R "$USER:$USER" /srv/supabase-data
```
Боевой `pg_restore` — только с явного согласия владельца.

#### 8) Swap при RAM ≤ 4 ГБ
Добавить swap ≥ 2–4 ГиБ.

### Ограничения
- Не открывать Postgres/Studio в интернет.
- Не коммитить и не присылать секреты.
- Не трогать прод-VPS `91.229.11.147` без согласия.
- Не удалять данные/диски/старые ВМ.
- Не менять DNS самостоятельно.
- Не считать задачу выполненной, если поднят только файл дампа без healthy Compose.

### Критерии готовности — что вернуть
1. Публичный IPv4, ОС, vCPU/RAM/диск, SSH-логин.
2. Подтверждение ключа в `authorized_keys`.
3. Версии docker / compose.
4. `docker compose ps` — контейнеры up.
5. `ss` + `ufw` — снаружи только 22/80/443.
6. Код `http://127.0.0.1:8000/health`.
7. `curl -I https://supabase…` (**401**) или до DNS — `curl -vk https://<IP>/`.
8. Путь `/srv/supabase-data/restore/`.
9. Список: сделано / ждёт владельца (секреты, дамп, DNS, VPS).

---
Это техническое задание для выполнения ассистентом reg.ru.
