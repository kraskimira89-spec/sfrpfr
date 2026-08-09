# -*- coding: utf-8 -*-
"""Собрать компактные превью дипломов/сертификатов для галереи на главной."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pip install pymupdf") from exc

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "prize"
OUT = ROOT / "scripts" / "assets" / "awards"
MANIFEST = OUT / "manifest.json"

# Единый кадр для галереи (некрупный).
FRAME_W, FRAME_H = 480, 360
JPEG_QUALITY = 82

KEYWORDS = (
    "диплом",
    "сертификат",
    "благодар",
    "грамота",
    "лауреат",
    "приз",
    "наград",
    "certificate",
    "coursera",
    "участник",
    "победитель",
    "почёт",
    "почет",
)

SKIP_EXACT = {
    "перечень-база добровольцев.xlsx",
    "Белозерцева 2.jpeg",
}


def should_skip(path: Path) -> bool:
    low = path.name.lower()
    # Stepik у Богдановского и любые stepik-сертификаты не показываем в галерее.
    if "stepik" in low:
        return True
    if "белозерцева 2" in low:
        return True
    return False


def frame_digest(frame: Image.Image) -> str:
    import hashlib
    import io

    buf = io.BytesIO()
    frame.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return hashlib.md5(buf.getvalue()).hexdigest()


def collect_stepik_digests() -> set[str]:
    """Хэши превью файлов Stepik — чтобы отсечь те же сертификаты под другими именами."""
    digests: set[str] = set()
    for path in SRC.iterdir():
        if not path.is_file() or "stepik" not in path.name.lower():
            continue
        if path.stat().st_size < 1024:
            continue
        try:
            raw = load_image(path)
            if raw is None:
                continue
            digests.add(frame_digest(fit_frame(raw)))
            print("BLACKLIST stepik", path.name)
        except Exception as exc:  # noqa: BLE001
            print("FAIL stepik", path.name, exc)
    return digests


def slugify(name: str) -> str:
    base = Path(name).stem
    base = unicodedata.normalize("NFKC", base)
    base = base.lower().replace("ё", "е")
    # транслит упрощённый для URL
    table = str.maketrans(
        {
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "g",
            "д": "d",
            "е": "e",
            "ж": "zh",
            "з": "z",
            "и": "i",
            "й": "y",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "h",
            "ц": "c",
            "ч": "ch",
            "ш": "sh",
            "щ": "sch",
            "ъ": "",
            "ы": "y",
            "ь": "",
            "э": "e",
            "ю": "yu",
            "я": "ya",
        }
    )
    latin = base.translate(table)
    latin = re.sub(r"[^a-z0-9]+", "-", latin).strip("-")
    return (latin or "award")[:72]


def title_from_name(name: str) -> str:
    """Сырое имя файла (для ключей дублей до pretty)."""
    t = Path(name).stem
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*\(\d+\)\s*$", "", t)
    return t[:120]


# Единый стандарт подписей: «Тип · тема». ФИО — только в note.
TITLE_BY_SOURCE: dict[str, str] = {
    "Диплом Лопакова.pdf": "Диплом",
    "Диплом Лопакова Наталия Федоровна.pdf": "Диплом · социальный проект",
    "Лопаковой Наталии Федоровне -Диплом участника (1).pdf": "Диплом участника",
    "Сертификат Лопакова Наталия Федоровна.jpg": "Сертификат",
    "Сертификат участника Лопакова Наталия Федоровна.pdf": "Сертификат участника",
    "Сертификат Цифровая трансформация Лопакова.pdf": "Сертификат · Цифровая трансформация",
    "Богдановский Сергей Викторович.jpg": "Награда",
    "Богдановский Сергей Викторович-14.png": "Награда · волонтёрство",
    "Богдановский  сертификат о прохождении онлайн-курса Страх и ненависть к презентациям.pdf": "Сертификат · онлайн-курс по презентациям",
    "Волонтеры СЕРТИФИКАТ Богдановский Сергей Викторович.pdf": "Сертификат · волонтёры",
    "Добровольцы России Богдановский Сергей Викторович.jpg": "Сертификат · Добровольцы России",
    "Доступная среда Богдановский Сергей Викторович.jpg": "Сертификат · доступная среда",
    "Сертификат Богдановский Сергей Викторович Добровольцы России.pdf": "Сертификат участника · Добровольцы России",
    "Сертификат Богдановский Сергей Викторович МыВместе.png": "Сертификат · МыВместе",
    "Сертификат Богдановский Сергей Викторович НеОДН.pdf": "Сертификат · НеОДН",
    "Сертификат за презентацию Богдановский С.В..pdf": "Сертификат · презентация",
    "Сертификат участника-2019 Богдановский.pdf": "Сертификат участника · 2019",
    "Траектория роста Богдановский С.В..jpg": "Сертификат · Траектория роста",
    "2019-12-02_104_Серитификат участника онлайн.pdf": "Сертификат участника · онлайн",
    "Благодарственное письмо Ласточка_1.png": "Благодарственное письмо · Ласточка",
    "Благодарственное письмо ЛДПР.pdf": "Благодарственное письмо · ЛДПР",
    "Благодарственное письмо Юные таланты.jpg": "Благодарственное письмо · Юные таланты",
    "Блдагодарность Лиза Алерт.jpg": "Благодарность · Лиза Алерт",
    "Взгляд.png": "Сертификат · Взгляд",
    "Диплом участника в Форме НКО Мозайка Иванова Е.А..pdf": "Диплом участника · Форма НКО «Мозаика»",
    "дипломы победителей-08.png": "Диплом победителя",
    "дипломы победителей-12.png": "Диплом победителя · 2",
    "Награждение СИБУР 2020.jpg": "Награда · СИБУР, 2020",
    "РИТМ Университет.jpg": "Сертификат · РИТМ Университет",
    "Сертификат Coursera DYZYWNM7B5KX.pdf": "Сертификат · Coursera",
    "Сертификат Волонтеры Конституции.pdf": "Сертификат · Волонтёры Конституции",
    "Сертификат Иванова.pdf": "Сертификат · Иванова",
    "Сертификат Территория РИТМА (1).jpeg": "Сертификат · Территория РИТМА",
    "Сертификат участника БФ Наше будущее.pdf": "Сертификат участника · БФ «Наше будущее»",
    "ТАГАНАЙ (1).jpg": "Диплом · «Таганай»",
}


def pretty_title(source_name: str) -> str:
    """Единый формат: «Тип» или «Тип · тема». Без ФИО и мусора из имени файла."""
    if source_name in TITLE_BY_SOURCE:
        return TITLE_BY_SOURCE[source_name]

    t = Path(source_name).stem
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("Серитификат", "Сертификат").replace("Блдагодарность", "Благодарность")
    t = t.replace("СЕРТИФИКАТ", "Сертификат").replace("Мозайка", "Мозаика")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*\(\d+\)\s*$", "", t)
    t = re.sub(r"_\d+$", "", t)
    t = re.sub(r"-\d{1,2}$", "", t)
    t = re.sub(r"^\d{4}-\d{2}-\d{2}[_\d]*_?", "", t)

    # ФИО убираем из заголовка — они в note.
    person_patterns = [
        r"Лопаков(?:а|ой|у|е|ы)?(?:\s+Натали[ияю]\s+Федоровн[аеы])?",
        r"Богдановск(?:ий|ого|ому|им)?(?:\s+Серге[йяю]\s+Викторовн?[аич]*)?",
        r"Богдановский\s*С\.?\s*В\.?",
        r"Иванов(?:а|ой)?\s*Е\.?\s*А\.?",
    ]
    for pat in person_patterns:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)

    t = re.sub(r"\s*[-–—:]\s*", " · ", t)
    t = re.sub(r"\s+", " ", t).strip(" ·.-_")
    if not t:
        return "Награда"

    # Тип документа в начале.
    kinds = [
        ("благодарственное письмо", "Благодарственное письмо"),
        ("благодарность", "Благодарность"),
        ("диплом участника", "Диплом участника"),
        ("диплом победителя", "Диплом победителя"),
        ("дипломы победителей", "Диплом победителя"),
        ("диплом", "Диплом"),
        ("сертификат участника", "Сертификат участника"),
        ("сертификат", "Сертификат"),
        ("награждение", "Награда"),
        ("грамота", "Грамота"),
    ]
    low = t.lower()
    for needle, label in kinds:
        if low.startswith(needle):
            rest = t[len(needle) :].strip(" ·.-")
            # Убрать служебные хвосты
            rest = re.sub(
                r"^(о прохождении онлайн-курса|за презентацию|о прохождении)\s+",
                "",
                rest,
                flags=re.IGNORECASE,
            ).strip(" ·.-")
            return f"{label} · {rest}" if rest else label
        if needle in low and not any(low.startswith(k[0]) for k in kinds):
            # тип не в начале — вынести вперёд
            rest = re.sub(re.escape(needle), " ", t, count=1, flags=re.IGNORECASE)
            rest = re.sub(r"\s+", " ", rest).strip(" ·.-")
            return f"{label} · {rest}" if rest else label

    # Без явного типа
    if t[:1].islower():
        t = t[:1].upper() + t[1:]
    return t[:100]


def is_candidate(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 1024:
        return False
    if path.name in SKIP_EXACT or should_skip(path):
        return False
    ext = path.suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
        return False
    low = path.name.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return True
    return any(k in low for k in KEYWORDS)


def normalize_title_key(title: str) -> str:
    t = title.lower().replace("ё", "е")
    t = re.sub(r"\s*\(\d+\)\s*", " ", t)
    t = re.sub(r"[^a-zа-я0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def fit_frame(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (247, 249, 251))
        bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")

    canvas = Image.new("RGB", (FRAME_W, FRAME_H), (247, 249, 251))
    fitted = ImageOps.contain(im, (FRAME_W, FRAME_H), Image.Resampling.LANCZOS)
    x = (FRAME_W - fitted.width) // 2
    y = (FRAME_H - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def load_image(path: Path) -> Image.Image | None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        doc = fitz.open(path)
        if doc.page_count < 1:
            doc.close()
            return None
        page = doc.load_page(0)
        # умеренный DPI — для превью
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        doc.close()
        return im
    return Image.open(path)


def person_note(name: str) -> str:
    low = name.lower()
    if "лопаков" in low:
        return "Лопакова Н. Ф."
    if "богданов" in low:
        return "Богдановский С. В."
    return ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("award-*.jpg"):
        old.unlink()

    items: list[dict] = []
    used_slugs: set[str] = set()
    seen_hashes: set[str] = set()
    seen_titles: set[str] = set()
    stepik_hashes = collect_stepik_digests()
    files = sorted(
        [p for p in SRC.iterdir() if is_candidate(p)],
        key=lambda p: (
            0 if "лопаков" in p.name.lower() else (1 if "богданов" in p.name.lower() else 2),
            p.name.lower(),
        ),
    )

    for path in files:
        try:
            raw = load_image(path)
            if raw is None:
                print("SKIP empty", path.name)
                continue
            frame = fit_frame(raw)
        except Exception as exc:  # noqa: BLE001
            print("FAIL", path.name, exc)
            continue

        note = person_note(path.name)
        title = pretty_title(path.name)
        title_key = normalize_title_key(title)
        # Дубликаты по итоговому названию (после нормализации).
        if title_key and title_key in seen_titles:
            print("SKIP title-dup", path.name, "->", title)
            continue

        digest = frame_digest(frame)
        if digest in stepik_hashes:
            print("SKIP stepik-content", path.name)
            continue
        if digest in seen_hashes:
            print("SKIP content-dup", path.name)
            continue

        slug = slugify(path.name)
        base = slug
        n = 2
        while slug in used_slugs:
            slug = f"{base}-{n}"
            n += 1
        used_slugs.add(slug)

        out_name = f"award-{slug}.jpg"
        out_path = OUT / out_name
        frame.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True)

        seen_hashes.add(digest)
        if title_key:
            seen_titles.add(title_key)

        items.append(
            {
                "src": f"/wp-content/uploads/sfrfr/awards/{out_name}",
                "title": title,
                "alt": title,
                "note": note,
                "source": path.name,
                "bytes": out_path.stat().st_size,
            }
        )
        print("OK", title, "|", path.name)

    # Стабильный порядок: сначала с именами экспертов, потом остальное
    def sort_key(it: dict) -> tuple:
        note = it.get("note") or ""
        pri = 0 if "Лопакова" in note else (1 if "Богдановский" in note else 2)
        return (pri, it["title"].lower())

    items.sort(key=sort_key)
    MANIFEST.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = [{k: v for k, v in it.items() if k in ("src", "title", "alt", "note") and v} for it in items]
    for it in compact:
        it.setdefault("alt", it.get("title", ""))
    (OUT / "home-data.json").write_text(
        json.dumps(compact, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"DONE {len(items)} -> {MANIFEST}")


if __name__ == "__main__":
    main()
