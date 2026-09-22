# Playbook: лид-магнит «Папка пенсионных документов»

Стратегия: [strategy-leadmagnet-pension-folder-2026-08.md](strategy-leadmagnet-pension-folder-2026-08.md) · задача [PUB-6](https://tracker.yandex.ru/PUB-6) · UTM: [playbook-leadmagnet-utm-tags.md](playbook-leadmagnet-utm-tags.md).

## URL

| URL | Назначение |
|-----|------------|
| https://proverkastaza.ru/chek-list-dokumentov/ | Посадочная выдача |
| https://proverkastaza.ru/pension-checklist-a4.pdf | **PDF для рассылки** (канон) |
| https://proverkastaza.ru/pension-checklist-a4-bw.pdf | PDF ч/б для офисной печати |
| https://proverkastaza.ru/chek-list-dokumentov/a4/ | Компактный лист A4 в браузере (noindex) |
| https://proverkastaza.ru/chek-list-dokumentov/pechat/ | Рабочая тетрадь 8 стр. (noindex) |

## Исходники

| Файл | Назначение |
|------|------------|
| `scripts/assets/leadmagnets/pension-folder-checklist.md` | Текст тетради 8 стр. |
| `scripts/assets/leadmagnets/pension-checklist-a4-one-page.md` | Текст листа A4 (1 стр.) |
| `docs/marketing-sales/spec-leadmagnet-a4-one-page-2026-08.md` | ТЗ для дизайнера / Figma |
| `scripts/assets/leadmagnets/pension-checklist-a4-standard.pdf` | PDF рассылки (канон) |
| `scripts/assets/leadmagnets/pension-checklist-a4-bw.pdf` | PDF ч/б |
| `scripts/assets/leadmagnets/pension-checklist-a4-preview.png` | Превью для лендинга |
| `scripts/build_leadmagnet_a4_pdf.py` | Пересборка PDF из HTML |
| `scripts/assets/trust/chek-list-dokumentov.html` | Посадочная |
| `scripts/assets/trust/chek-list-dokumentov-a4.html` | Печать A4 (1 стр.) |
| `scripts/assets/trust/chek-list-dokumentov-pechat.html` | Печать тетради (8 стр.) |
| Сид | `scripts/wp_seed_trust_pages_tz18.php` |

После правки текста/макета:

```powershell
.\.venv\Scripts\python.exe scripts/build_leadmagnet_a4_pdf.py
```

После деплоя на VPS (PDF копируется автоматически в `vps_deploy.sh`):

```bash
bash /opt/sfrfr/scripts/wp_seed_trust_pages_tz18.sh
bash /opt/sfrfr/scripts/wp_apply_landing_vps.sh
```

## Выдача MVP

1. Форма на `/chek-list-dokumentov/`: имя + канал (e-mail / MAX) + обязательное согласие ПДн + необязательный маркетинг.  
2. REST: `POST /wp-json/proverkastaza/v1/lead-magnet` (MU `sfrfr-lead-magnet.php`).  
3. Всегда выдаётся ссылка на **`/pension-checklist-a4.pdf`** (+ тетрадь 8 стр. в письме).  
4. В e-mail и в MAX (фраза **«Нужен чек-лист документов»** / `/checklist`) — **перечень для анализа дела**: выписка ИЛС + трудовая / ЭТК (канон `documents-checklist.md` §1) + ссылки на PDF.  
5. В письме и в PDF — блок **«Куда обратиться»**: сайт, чат-бот MAX, канал MAX, личный чат (+ QR на листе A4).  
6. При e-mail — письмо с перечнем и ссылками; маркетинг не шлётся без отдельного согласия.  
7. Микродействия после: **«ИЛС получил(а)»** / **«Есть расхождение»** / **«Нужна проверка документов»**.

Маркер в HTML: форма уже встроена (не shortcode). Honeypot + rate limit 8 / 15 мин.

Код бота: `src/sfrfr/services/lead_magnet_checklist.py` + обработка в `integrations/max/handler.py`.

## Оператор

- Не просить сканы в чат.  
- Не продавать диагностику в первом сообщении после выдачи.  
- После микродействия — сценарии из [`ils-self-check-checklist.md`](../../scripts/assets/copy/ils-self-check-checklist.md).  
- Диагностика: 3 000 ₽; решает СФР.

## Метрика (цели)

| Цель | Событие |
|------|---------|
| `checklist_view` | Просмотр посадочной |
| `checklist_cta_click` | Клик «Получить чек-лист» |
| `checklist_max_click` | Переход в MAX с страницы |
| `checklist_print_open` | Открытие версии для печати |
| `checklist_download` | Скачивание PDF |

## Что ещё сделать

- [x] Сверстать печатную HTML-тетрадь A4 (`chek-list-dokumentov-pechat.html`, 8 стр.)  
- [x] Посадочная + форма + REST `lead-magnet` (ПДн / маркетинг раздельно, honeypot, rate limit, nonce)  
- [x] PDF A4 для рассылки (`pension-checklist-a4-standard.pdf`, деплой → `/pension-checklist-a4.pdf`)  
- [x] QR и ссылки на сайте PDF: сайт / чат-бот / канал / личный чат  
- [ ] Теги leadmagnet в amo / кабинете  
- [ ] 2–3 статьи-проводника со ссылкой на страницу  
- [ ] Ссылка с главной / релевантных trust-страниц (по согласованию)  
- [ ] A/B H1 после 30–50 выдач  

### Backend (канон MU)

`scripts/wp-mu-plugins/sfrfr-lead-magnet.php`:

- nonce `X-WP-Nonce` + bootstrap;
- honeypot `company`;
- rate limit 8 / 15 мин по IP;
- отдельные флаги ПДн (обязательно) и маркетинг;
- журнал `sfrfr_lead_magnet_audit` — хеши контакта/IP, без сырых ПДн в option;
- письмо оператору + e-mail клиенту: перечень для анализа, PDF, блок «Куда обратиться» (сайт / чат-бот / канал / личный чат); без рекламы, если нет marketing_consent.
