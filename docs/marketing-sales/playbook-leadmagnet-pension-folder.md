# Playbook: лид-магнит «Папка пенсионных документов»

Стратегия: [strategy-leadmagnet-pension-folder-2026-08.md](strategy-leadmagnet-pension-folder-2026-08.md) · задача [PUB-6](https://tracker.yandex.ru/PUB-6).

## URL

| URL | Назначение |
|-----|------------|
| https://proverkastaza.ru/chek-list-dokumentov/ | Посадочная выдача |
| https://proverkastaza.ru/chek-list-dokumentov/pechat/ | Версия для печати / чтения (noindex) |

## Исходники

| Файл | Назначение |
|------|------------|
| `scripts/assets/leadmagnets/pension-folder-checklist.md` | Текст PDF (канон) |
| `scripts/assets/trust/chek-list-dokumentov.html` | Посадочная |
| `scripts/assets/trust/chek-list-dokumentov-pechat.html` | Печать |
| Сид | `scripts/wp_seed_trust_pages_tz18.php` |

После деплоя на VPS:

```bash
bash /opt/sfrfr/scripts/wp_seed_trust_pages_tz18.sh
bash /opt/sfrfr/scripts/wp_apply_landing_vps.sh
```

## Выдача MVP

1. Форма на `/chek-list-dokumentov/`: имя + канал (e-mail / MAX) + обязательное согласие ПДн + необязательный маркетинг.  
2. REST: `POST /wp-json/proverkastaza/v1/lead-magnet` (MU `sfrfr-lead-magnet.php`).  
3. Всегда выдаётся ссылка на `/chek-list-dokumentov/pechat/` (веб-тетрадь).  
4. При e-mail — письмо со ссылкой; маркетинг не шлётся без отдельного согласия.  
5. Микродействия после: **«ИЛС получил(а)»** / **«Есть расхождение»** / **«Нужна проверка документов»**.

Маркер в HTML: форма уже встроена (не shortcode). Honeypot + rate limit 8 / 15 мин.

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
| `checklist_download` | (позже) скачивание PDF |

## Что ещё сделать

- [x] Сверстать печатную HTML-тетрадь A4 (`chek-list-dokumentov-pechat.html`, 8 стр.)  
- [ ] Отдельный PDF-файл из Canva (опционально; сейчас «Печать → PDF» из браузера)  
- [ ] WPForms / выдача по e-mail с раздельными согласиями  
- [ ] Теги leadmagnet в amo / кабинете  
- [ ] 2–3 статьи-проводника со ссылкой на страницу  
- [ ] Ссылка с главной / релевантных trust-страниц (по согласованию)
