# Examples — VisualMatrix (эталоны)

Канонические JSON лежат в `prompts/visual/examples/*.json` (создаются в Agent mode).
Ниже — содержимое для ручного копирования, пока файлы `.json` не записаны.

## checklist-documents (MAX 1:1)

```json
{
  "topic": "Как собрать документы для проверки стажа",
  "audience": "пенсионер или взрослый ребёнок, помогающий родителю",
  "problem": "документы лежат хаотично, непонятно с чего начать",
  "emotionBefore": "перегрузка и растерянность",
  "desiredState": "порядок, ясность, спокойный контроль",
  "coreMessage": "сначала соберите документы в одну понятную систему папок",
  "metaphor": "четыре аккуратные папки вместо хаотичной стопки бумаг",
  "action": "руки взрослого человека раскладывают нейтральные листы по папкам",
  "subject": "светлый стол, четыре папки, чек-лист с пустыми чекбоксами, ручка",
  "visualStyle": "realistic editorial top-down still life photography",
  "mood": "calm, respectful, organized",
  "brandPalette": "soft white background with restrained navy blue and green accents",
  "composition": "top-down composition, objects in lower and central areas",
  "textSafeArea": "upper right third",
  "platform": "MAX",
  "aspectRatio": "1:1",
  "prohibitions": ["personal documents", "banknotes", "official logos", "readable text on papers"]
}
```

## archive-request (blog 16:9)

См. методику: архивные коробки, карточка периода, стрелка маршрута — без гарантии результата.

## safe-document-upload (MAX 1:1)

Метафора: чат снаружи, папка в защищённой ячейке **кабинета на сайте** (вложения в чат принимаются).

## checklist-return (blog 16:9)

Приоткрытая дверь, папка и чек-лист — «не давить, оставить путь вернуться».

## family-support (site 4:3)

Две пары рук / пожилой и взрослый ребёнок над чек-листом — достоинство, не опека.

После Agent mode: файлы `*.json` + `checklist-documents.compiled.json` + PNG в `docs/brand/assets/`.
