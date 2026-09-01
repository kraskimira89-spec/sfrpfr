"""Постраничный ingest v2: text layer → Vision OCR → Tesseract fallback."""

from __future__ import annotations

import base64
import io
import os
from datetime import UTC, datetime
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.services.document_ingest import run_ingest_pipeline, sha256_hex
from sfrfr.services.file_security import MAX_PDF_PAGES, validate_file_bytes

DEFAULT_MIN_CHARS_PER_PAGE = 80
DEFAULT_MIN_CHARS_DOCUMENT = 120
DEFAULT_OCR_DPI = 200
DEFAULT_MAX_PAGES = 40


def run_document_ingest_v2(
    *,
    data: bytes,
    filename: str,
    content_type: str | None,
    doc_type: str | None,
    active_scenarios: set[str],
    duplicate_checksum: bool,
    case_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Извлечь текст постранично и вернуть результат для worker-а."""
    allow_signed = (doc_type or "").strip().lower() in {
        "client_signed_application",
        "client_signed_appeal",
    }
    security = validate_file_bytes(
        data,
        filename=filename,
        declared_content_type=content_type,
        allow_signed=allow_signed,
    )
    if not security.ok:
        return {
            "ingest_status": "blocked_security",
            "progress_percent": 100,
            "current_stage": "blocked_security",
            "progress_message": security.client_message or "Нужна повторная загрузка.",
            "ingest_review_required": False,
            "pages": [],
            "extracted_text": "",
            "manifest": _manifest(
                case_id=case_id,
                document_id=document_id,
                filename=filename,
                checksum="",
                mime=security.detected_mime,
                pages=[],
                review_required=False,
            ),
        }

    page_results = _extract_pages(data, filename, security.detected_mime)
    page_count = len(page_results)
    max_pages = min(
        _env_int("INGEST_MAX_PAGES", DEFAULT_MAX_PAGES),
        MAX_PDF_PAGES,
    )
    if page_count > max_pages:
        return {
            "ingest_status": "blocked_security",
            "progress_percent": 100,
            "current_stage": "blocked_security",
            "progress_message": (
                "Слишком много страниц в файле. Разделите документ или загрузите нужные страницы."
            ),
            "ingest_review_required": False,
            "page_count": page_count,
            "pages": page_results,
            "extracted_text": "",
            "manifest": _manifest(
                case_id=case_id,
                document_id=document_id,
                filename=filename,
                checksum="",
                mime=security.detected_mime,
                pages=page_results,
                review_required=False,
            ),
        }

    extracted_text = "\n\n".join(
        f"## Страница {index}\n{page['text']}".strip()
        for index, page in enumerate(page_results, start=1)
        if page.get("text")
    )
    plain_text = "\n".join(str(page.get("text") or "") for page in page_results)
    min_document_chars = _env_int("INGEST_MIN_CHARS_DOC", DEFAULT_MIN_CHARS_DOCUMENT)
    failed_pages = sum(1 for page in page_results if page.get("source") == "failed")
    needs_review = (
        failed_pages > 0
        or _compact_length(plain_text) < min_document_chars
        or "[ocr_error]" in plain_text
        or "[ocr_empty]" in plain_text
    )
    if needs_review:
        pipeline: dict[str, Any] = {
            "ingest_status": "manual_review",
            "current_stage": "manual_review",
            "progress_message": (
                "Текст или часть страниц требуют проверки специалистом перед распознаванием."
            ),
            "mime_verified": security.detected_mime,
            "checksum_sha256": sha256_hex(data),
            "placement_suggestion": None,
            "quality_report": {
                "overall_score": 0.25,
                "issues": ["ingest_review_required"],
                "recommended_action": "manual_review",
                "client_message": (
                    "Файл принят на проверку. Специалист сверит страницы и текст."
                ),
                "char_count": _compact_length(plain_text),
            },
        }
    else:
        pipeline = run_ingest_pipeline(
            data=data,
            filename=filename,
            content_type=content_type,
            doc_type=doc_type,
            preview_text=plain_text,
            active_scenarios=active_scenarios,
            duplicate_checksum=duplicate_checksum,
        )
    if pipeline.get("ingest_status") == "blocked_security":
        needs_review = False
    pipeline["progress_percent"] = 95
    quality = dict(pipeline.get("quality_report") or {})
    quality.update(
        {
            "page_count": page_count,
            "failed_pages": failed_pages,
            "total_chars": _compact_length(plain_text),
            "needs_ingest_review": needs_review,
        }
    )
    pipeline["quality_report"] = quality
    pipeline["ingest_review_required"] = needs_review
    pipeline["page_count"] = page_count
    pipeline["pages"] = page_results
    pipeline["extracted_text"] = extracted_text
    pipeline["ingest_engine"] = _engines_used(page_results)
    pipeline["manifest"] = _manifest(
        case_id=case_id,
        document_id=document_id,
        filename=filename,
        checksum=str(pipeline.get("checksum_sha256") or ""),
        mime=security.detected_mime,
        pages=page_results,
        review_required=needs_review,
    )
    return pipeline


def _extract_pages(data: bytes, filename: str, detected_mime: str | None) -> list[dict[str, Any]]:
    suffix = os.path.splitext(filename or "")[1].lower()
    if detected_mime == "application/pdf" or suffix == ".pdf":
        return _extract_pdf_pages(data)
    if detected_mime and detected_mime.startswith("image/"):
        text, source, engine, error = _ocr_image(data, filename)
        return [_page(1, text, source, engine, error)]
    if suffix == ".docx":
        text = _extract_docx(data)
        return [_page(1, text, "plain_file", None, None if text else "docx_empty")]
    return [_page(1, "", "failed", None, "unsupported_document")]


def _extract_pdf_pages(data: bytes) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages: list[dict[str, Any]] = []
        min_chars = _env_int("INGEST_MIN_CHARS_PER_PAGE", DEFAULT_MIN_CHARS_PER_PAGE)
        for index, pdf_page in enumerate(reader.pages, start=1):
            text = _normalize(pdf_page.extract_text() or "")
            if _compact_length(text) >= min_chars:
                pages.append(_page(index, text, "text_layer", None, None))
                continue
            rendered = _render_pdf_page(data, index)
            if rendered is None:
                pages.append(_page(index, text, "failed", None, "pdf_render_failed"))
                continue
            ocr_text, source, engine, error = _ocr_image(rendered, f"page-{index}.png")
            pages.append(_page(index, ocr_text or text, source, engine, error))
        return pages
    except Exception as exc:  # noqa: BLE001
        return [_page(1, "", "failed", None, f"pdf_read:{type(exc).__name__}")]


def _render_pdf_page(data: bytes, page_number: int) -> bytes | None:
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(
            data,
            dpi=_env_int("INGEST_OCR_DPI", DEFAULT_OCR_DPI),
            first_page=page_number,
            last_page=page_number,
            fmt="png",
        )
        if not images:
            return None
        buffer = io.BytesIO()
        images[0].save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document

        document = Document(io.BytesIO(data))
        return _normalize("\n".join(paragraph.text for paragraph in document.paragraphs))
    except Exception:  # noqa: BLE001
        return ""


def _ocr_image(data: bytes, filename: str) -> tuple[str, str, str | None, str | None]:
    settings = get_settings()
    engine = os.getenv("INGEST_OCR_ENGINE", settings.ocr_engine).strip().lower()
    use_vision = engine in {"auto", "vision"}
    fallback = _env_bool("INGEST_VISION_FALLBACK_TESSERACT", True)
    if use_vision and _vision_configured():
        try:
            text = _vision_ocr(data)
            if text:
                return _normalize(text), "ocr_vision", "yandex_vision", None
            if engine == "vision" and not fallback:
                return "", "failed", "yandex_vision", "vision_empty"
        except Exception as exc:  # noqa: BLE001
            if engine == "vision" and not fallback:
                return "", "failed", "yandex_vision", type(exc).__name__
    if engine == "vision" and not fallback and not _vision_configured():
        return "", "failed", "yandex_vision", "vision_not_configured"
    text = _tesseract_ocr(data, filename)
    if text:
        return _normalize(text), "ocr_tesseract", "tesseract", None
    return "", "failed", "tesseract", "tesseract_empty"


def _vision_configured() -> bool:
    settings = get_settings()
    return bool(
        (os.getenv("YANDEX_VISION_API_KEY") or settings.yandex_api_key).strip()
        and (os.getenv("YANDEX_VISION_FOLDER_ID") or settings.yandex_folder_id).strip()
    )


def _vision_ocr(data: bytes) -> str:
    import httpx

    settings = get_settings()
    api_key = (os.getenv("YANDEX_VISION_API_KEY") or settings.yandex_api_key).strip()
    folder_id = (os.getenv("YANDEX_VISION_FOLDER_ID") or settings.yandex_folder_id).strip()
    response = httpx.post(
        "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze",
        headers={"Authorization": f"Api-Key {api_key}"},
        json={
            "folderId": folder_id,
            "analyzeSpecs": [
                {
                    "content": base64.b64encode(data).decode("ascii"),
                    "features": [
                        {
                            "type": "TEXT_DETECTION",
                            "textDetectionConfig": {"languageCodes": ["ru", "en"]},
                        }
                    ],
                }
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    return _collect_vision_text(response.json())


def _collect_vision_text(value: Any) -> str:
    chunks: list[str] = []
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
        for child in value.values():
            chunks.append(_collect_vision_text(child))
    elif isinstance(value, list):
        for child in value:
            chunks.append(_collect_vision_text(child))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _tesseract_ocr(data: bytes, filename: str) -> str:
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(data))
        try:
            text = pytesseract.image_to_string(
                image,
                lang=get_settings().tesseract_lang,
            )
            return (text or "").strip()
        finally:
            image.close()
    except Exception:  # noqa: BLE001
        return ""


def _page(
    number: int,
    text: str,
    source: str,
    engine: str | None,
    error: str | None,
) -> dict[str, Any]:
    normalized = _normalize(text)
    return {
        "page": number,
        "source": source,
        "char_count": _compact_length(normalized),
        "engine": engine,
        "error": error,
        "text": normalized,
    }


def _manifest(
    *,
    case_id: str,
    document_id: str,
    filename: str,
    checksum: str,
    mime: str | None,
    pages: list[dict[str, Any]],
    review_required: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "doc_id": document_id,
        "case_id": case_id,
        "original_name": filename,
        "content_hash": f"sha256:{checksum}" if checksum else "",
        "mime": mime,
        "page_count": len(pages),
        "needs_ingest_review": review_required,
        "pages": [
            {key: page.get(key) for key in ("page", "source", "char_count", "engine", "error")}
            for page in pages
        ],
        "totals": {
            "chars": sum(int(page.get("char_count") or 0) for page in pages),
            "text_layer_pages": sum(page.get("source") == "text_layer" for page in pages),
            "ocr_pages": sum(str(page.get("source") or "").startswith("ocr_") for page in pages),
            "failed_pages": sum(page.get("source") == "failed" for page in pages),
        },
        "created_at": datetime.now(UTC).isoformat(),
    }


def _engines_used(pages: list[dict[str, Any]]) -> str | None:
    engines = sorted({str(page["engine"]) for page in pages if page.get("engine")})
    return ",".join(engines) or None


def _normalize(value: str) -> str:
    return "\n".join(line.strip() for line in value.replace("\r\n", "\n").splitlines()).strip()


def _compact_length(value: str) -> int:
    return len("".join(value.split()))


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(value, 1)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}
