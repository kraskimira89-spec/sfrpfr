# 2026-08-05 — ТЗ-22: опыт и награды

## Что сделано

- Добавлено [ТЗ-22](../specs/22-trust-experience-awards.md).
- В блоке «Кто оказывает услугу»: строка об опыте 8 лет (по запросу владельца).
- Подблок «Награды и профессиональные материалы» со слайдером (`sfrfr-awards.js`).
- Пока `#sfrfr-awards-data` = `[]` — нейтральная заглушка, без пустого UI.

## Как добавить фото позже

1. Подготовить WebP, убрать лишние ПДн/QR/номера.
2. Выложить в `wp-content/uploads/sfrfr/awards/`.
3. В `scripts/assets/sfrfr-home.html` заполнить JSON, например:

```json
[
  {
    "src": "/wp-content/uploads/sfrfr/awards/example.webp",
    "srcset": "/wp-content/uploads/sfrfr/awards/example.webp 560w",
    "alt": "Краткое описание документа без лишних ПДн",
    "title": "Название материала",
    "year": "2020",
    "note": "Краткое пояснение без гарантий перерасчёта."
  }
]
```

4. Применить главную на VPS (`wp_apply_landing_vps.sh` / деплой).
