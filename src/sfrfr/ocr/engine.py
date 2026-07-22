"""OCR: текст из txt/изображений/PDF (Tesseract + pypdf)."""

from __future__ import annotations

from pathlib import Path

from sfrfr.core.config import get_settings

_TEXT_SUFFIXES = {".txt", ".md", ".csv"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def extract_text(path: Path | str) -> str:
    """Извлечь текст из файла. При ошибках OCR — понятное сообщение, без падения пайплайна."""
    file_path = Path(path)
    if not file_path.exists():
        return f"[ocr_error] файл не найден: {file_path.name}"

    suffix = file_path.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        return file_path.read_text(encoding="utf-8", errors="ignore").strip()

    if suffix == ".pdf":
        return _extract_pdf(file_path)

    if suffix in _IMAGE_SUFFIXES:
        return _extract_image(file_path)

    # неизвестный тип — пробуем как текст
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return f"[ocr_error] неподдерживаемый тип: {suffix or 'unknown'}"


def extract_texts(paths: list[Path | str]) -> list[str]:
    return [extract_text(p) for p in paths]


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "[ocr_error] pypdf не установлен"

    try:
        reader = PdfReader(str(path))
        chunks = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n".join(c for c in chunks if c).strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001
        return f"[ocr_error] pdf: {exc}"

    # текстового слоя нет — пробуем rasterize + tesseract (нужен poppler)
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return "[ocr_empty] PDF без текстового слоя (pdf2image недоступен)"

    try:
        images = convert_from_path(str(path), dpi=200)
    except Exception as exc:  # noqa: BLE001
        return f"[ocr_error] pdf2image: {exc}"

    parts = [_ocr_pil(img) for img in images]
    joined = "\n".join(p for p in parts if p).strip()
    return joined or "[ocr_empty] PDF: текст не распознан"


def _extract_image(path: Path) -> str:
    try:
        from PIL import Image
    except ImportError:
        return "[ocr_error] pillow не установлен"

    try:
        image = Image.open(path)
    except Exception as exc:  # noqa: BLE001
        return f"[ocr_error] image open: {exc}"

    text = _ocr_pil(image)
    return text or f"[ocr_empty] изображение без текста: {path.name}"


def _ocr_pil(image: object) -> str:
    settings = get_settings()
    try:
        import pytesseract
    except ImportError:
        return "[ocr_error] pytesseract не установлен"

    try:
        return (pytesseract.image_to_string(image, lang=settings.tesseract_lang) or "").strip()
    except Exception as exc:  # noqa: BLE001
        # часто: нет бинарника tesseract в PATH
        return f"[ocr_error] tesseract: {exc}"
