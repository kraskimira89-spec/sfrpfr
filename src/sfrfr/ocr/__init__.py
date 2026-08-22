"""OCR-контур: трудовые книжки, архивные справки, ИЛС."""

from sfrfr.ocr.engine import extract_text, extract_text_from_bytes, extract_texts

__all__ = ["extract_text", "extract_text_from_bytes", "extract_texts"]
