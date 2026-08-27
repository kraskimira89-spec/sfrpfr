# Утверждённые визуальные активы бренда

Именование: `viz-<slug>-<variant>.ext`. Ссылка из брифа в `../visualizations/`.

Перед публикацией сверять с [brand-platform-v2.md](../brand-platform-v2.md) §9–10.
Текст на картинках не ставим — подписи в вёрстке.

Референсы: `assets/proverka-stazha-cover-1200x640*.png`, `assets/sfrfr-logo-transparent.png`.

## Каталог

| Файл | Страница | Статус |
|------|----------|--------|
| `viz-family-digital-support-16x9.png` | `/`, `/pomoch-rodstvenniku-proverit-stazh/` | на сайте |
| `viz-family-digital-support-1x1.png` | посты | архив |
| `viz-diagnostika-16x9.png` / `1x1` | `/proverka-stazha/` | на сайте (16:9) |
| `viz-soprovozhdenie-16x9.png` / `1x1` | `/kak-rabotaem/` | на сайте (16:9) |
| `viz-pod-kluch-16x9.png` / `1x1` | запас | на согласовании |
| `viz-severnyy-stazh-16x9.png` / `1x1` | `/proverka-severnogo-stazha/` | на сайте |
| `viz-pered-pensiey-16x9.png` | `/proverka-stazha-pered-pensiey/` | на сайте |
| `viz-tarify-16x9.png` | `/tarify/` | на сайте |
| `viz-kabinet-16x9.png` / `1x1` | кабинет / инструкция | запас |
| `viz-kontakty-16x9.png` | `/kontakty/` | на сайте |
| `viz-otzyvy-16x9.png` | `/otzyvy/` | на сайте |
| `viz-stazh-do-2002-16x9.png` | `/stazh-do-2002/` | на сайте |
| `viz-vk-community-cover-1920x768.png` | обложка сообщества ВК | **1920×768** (мин. ВК 960×384); не шаблон zip 911×364 |
| `viz-meta-checklist-documents-1x1 хаос папки порядок.png` | посты / сбор документов | **Хаос → Папки → Порядок** (не диагностика) |
| `viz-meta-archive-request-16x9.png` | блог / архивная справка | черновик ИИ |
| `viz-meta-safe-document-upload-1x1.png` | MAX / безопасная передача | черновик ИИ |
| `viz-meta-checklist-return-16x9 замешательство  уважение возврат.png` | блог / бережный возврат | **Замешательство → Уважение → Возврат** |
| `viz-meta-family-support-4x3.png` | сайт / родственник помогает | черновик ИИ |

Исходники без слогана (`viz-meta-*-16x9.png` / `1x1.png` без суффикса) — для новой вёрстки текста. В посты брать файл **со слоганом в имени**.

Мета-обложки: матрицы в `prompts/visual/examples/`, брифы `viz-meta-*.md`. Приёмка человека обязательна.

Копирование на VPS: `wp_apply_landing_vps.sh` → `uploads/sfrfr/brand/`.

## Раскладка на страницах услуг

Как на главной: `.sfrfr-wrap.sfrfr-hero__grid` — текст/CTA слева, `.sfrfr-illustration` справа.
