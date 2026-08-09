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
}


def should_skip(path: Path) -> bool:
    low = path.name.lower()
    # Stepik у Богдановского и любые stepik-сертификаты не показываем в галерее.
    if "stepik" in low:
        return True
    return False


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
    t = Path(name).stem
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*\(\d+\)\s*$", "", t)
    return t[:120]


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
    import hashlib

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("award-*.jpg"):
        old.unlink()

    items: list[dict] = []
    used_slugs: set[str] = set()
    seen_hashes: set[str] = set()
    seen_titles: set[str] = set()
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

        title = title_from_name(path.name)
        title_key = normalize_title_key(title)
        # Дубликаты по имени (например «(1)» / «(2)»).
        if title_key and title_key in seen_titles:
            print("SKIP title-dup", path.name)
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

        digest = hashlib.md5(out_path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            out_path.unlink(missing_ok=True)
            used_slugs.discard(slug)
            print("SKIP content-dup", path.name)
            continue

        seen_hashes.add(digest)
        if title_key:
            seen_titles.add(title_key)

        note = person_note(path.name)
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
        print("OK", out_name, out_path.stat().st_size)

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
