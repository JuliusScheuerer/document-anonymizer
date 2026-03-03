"""Web frontend routes serving Jinja2 templates."""

import base64
import binascii
import html
import time
from pathlib import Path
from typing import Annotated, TypedDict

import structlog
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.api.dependencies import get_analyzer, get_anonymizer
from document_anonymizer.document.pdf_handler import (
    IncompleteRedactionError,
    extract_text_from_pdf,
    redact_pdf,
)
from document_anonymizer.document.text_handler import detect_pii_in_text
from document_anonymizer.security.validation import (
    FileValidationError,
    validate_file_content,
    validate_pdf_structure,
)

logger = structlog.get_logger(__name__)


class _EntityHighlight(TypedDict):
    entity_type: str
    start: int
    end: int
    score: float
    text: str


_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

web_router = APIRouter(tags=["web"])


async def _require_htmx_header(request: Request) -> None:
    """CSRF protection: require HX-Request header on POST endpoints.

    HTMX sends this header automatically. Cross-origin forms cannot set
    custom headers, so this blocks CSRF attacks without needing tokens.
    """
    if request.method == "POST" and not request.headers.get("HX-Request"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Missing required header")


@web_router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Main page with upload/paste interface."""
    strategies = [s.value for s in AnonymizationStrategy]
    return templates.TemplateResponse(request, "index.html", {"strategies": strategies})


_MAX_TEXT_LENGTH = 100_000


@web_router.post(
    "/detect",
    response_class=HTMLResponse,
    dependencies=[Depends(_require_htmx_header)],
)
async def detect_form(
    request: Request,
    text: Annotated[str, Form(max_length=_MAX_TEXT_LENGTH)] = "",
    score_threshold: Annotated[float, Form(ge=0.0, le=1.0)] = 0.35,
    file: UploadFile | None = File(default=None),  # noqa: B008
    analyzer: AnalyzerEngine = Depends(get_analyzer),  # noqa: B008
) -> HTMLResponse:
    """Handle detection form submission, return results fragment."""
    start = time.perf_counter()
    is_pdf = False
    pdf_b64 = ""

    # Handle file upload
    if file and file.filename:
        content = await file.read()
        try:
            mime_type = validate_file_content(content, filename=file.filename)
        except FileValidationError as e:
            return templates.TemplateResponse(
                request, "error_fragment.html", {"error": str(e)}
            )

        if mime_type == "application/pdf":
            try:
                validate_pdf_structure(content)
            except FileValidationError as e:
                return templates.TemplateResponse(
                    request, "error_fragment.html", {"error": str(e)}
                )
            text = extract_text_from_pdf(content)
            is_pdf = True
            pdf_b64 = base64.b64encode(content).decode()
        else:
            text = content.decode("utf-8", errors="replace")

    if not text.strip():
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": "Bitte Text eingeben oder Datei hochladen."},
        )

    try:
        results = detect_pii_in_text(analyzer, text, score_threshold=score_threshold)

        entities: list[_EntityHighlight] = [
            {
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": round(r.score, 3),
                "text": text[r.start : r.end],
            }
            for r in results
        ]

        highlighted = _build_highlighted_text(text, entities)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return templates.TemplateResponse(
            request,
            "results.html",
            {
                "entities": entities,
                "entity_count": len(entities),
                "original_text": text,
                "highlighted_text": highlighted,
                "processing_time_ms": round(elapsed_ms, 1),
                "score_threshold": score_threshold,
                "strategies": [s.value for s in AnonymizationStrategy],
                "is_pdf": is_pdf,
                "pdf_b64": pdf_b64,
            },
        )
    except Exception:
        logger.exception("detect_form_error")
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": "Fehler bei der PII-Erkennung. Bitte versuchen Sie es erneut."},
        )


@web_router.post(
    "/anonymize-form",
    response_class=HTMLResponse,
    dependencies=[Depends(_require_htmx_header)],
)
async def anonymize_form(
    request: Request,
    text: Annotated[str, Form(max_length=_MAX_TEXT_LENGTH)] = "",
    strategy: str = Form(default="replace"),
    score_threshold: Annotated[float, Form(ge=0.0, le=1.0)] = 0.35,
    is_pdf: bool = Form(default=False),
    pdf_b64: str = Form(default=""),
    analyzer: AnalyzerEngine = Depends(get_analyzer),  # noqa: B008
    anonymizer: AnonymizerEngine = Depends(get_anonymizer),  # noqa: B008
) -> HTMLResponse:
    """Handle anonymization form submission."""
    try:
        strat = AnonymizationStrategy(strategy)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": f"Unbekannte Strategie: {html.escape(strategy)}"},
        )

    try:
        start = time.perf_counter()

        detections = detect_pii_in_text(analyzer, text, score_threshold=score_threshold)
        anonymized = anonymize_text(anonymizer, text, detections, strategy=strat)

        entities_for_highlight: list[_EntityHighlight] = [
            {
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": round(r.score, 3),
                "text": text[r.start : r.end],
            }
            for r in detections
        ]
        highlighted_original = _build_highlighted_text(text, entities_for_highlight)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return templates.TemplateResponse(
            request,
            "anonymized.html",
            {
                "original_text": text,
                "anonymized_text": anonymized,
                "highlighted_original": highlighted_original,
                "entities_found": len(detections),
                "strategy": strategy,
                "processing_time_ms": round(elapsed_ms, 1),
                "score_threshold": score_threshold,
                "is_pdf": is_pdf,
                "pdf_b64": pdf_b64,
            },
        )
    except Exception:
        logger.exception("anonymize_form_error")
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": "Fehler bei der Anonymisierung. Bitte versuchen Sie es erneut."},
        )


@web_router.post("/redact-pdf")
async def redact_pdf_form(
    request: Request,
    pdf_b64: str = Form(...),
    score_threshold: Annotated[float, Form(ge=0.0, le=1.0)] = 0.35,
    analyzer: AnalyzerEngine = Depends(get_analyzer),  # noqa: B008
) -> Response:
    """Handle PDF redaction — returns redacted PDF for download."""
    try:
        pdf_bytes = base64.b64decode(pdf_b64)
        validate_file_content(pdf_bytes)
        validate_pdf_structure(pdf_bytes)
        redacted_bytes, _ = redact_pdf(
            analyzer, pdf_bytes, score_threshold=score_threshold
        )
    except binascii.Error:
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": "Ungültige PDF-Daten. Bitte laden Sie die Datei erneut hoch."},
            status_code=400,
        )
    except FileValidationError as e:
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": str(e)},
            status_code=400,
        )
    except IncompleteRedactionError as e:
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {
                "error": (
                    f"Unvollständige Schwärzung: {e.unredacted_count} von "
                    f"{e.total_count} erkannten PII-Entitäten konnten im PDF "
                    f"nicht visuell lokalisiert werden. "
                    f"Manuelle Überprüfung empfohlen."
                ),
            },
            status_code=422,
        )
    except Exception:
        logger.exception("redact_pdf_error")
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": "PDF-Schwärzung fehlgeschlagen."},
            status_code=500,
        )

    return Response(
        content=redacted_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=redacted.pdf"},
    )


def _build_highlighted_text(text: str, entities: list[_EntityHighlight]) -> str:
    """Build HTML with color-coded PII highlights.

    Escapes the full text first, then inserts <mark> tags at
    offset-adjusted positions to prevent XSS. Overlapping entities
    are merged (the first span wins, overlapping spans are skipped).
    """
    if not entities:
        return html.escape(text)

    # Sort by start position, then by longest span first for ties
    sorted_entities = sorted(entities, key=lambda e: (e["start"], -e["end"]))

    parts: list[str] = []
    last_end = 0

    for entity in sorted_entities:
        start = entity["start"]
        end = entity["end"]

        # Skip entities that overlap with the previous one
        if start < last_end:
            continue

        entity_type = entity["entity_type"]
        score = entity["score"]

        # Escape the gap between the last entity and this one
        parts.append(html.escape(text[last_end:start]))

        # Build the <mark> tag with escaped content
        original = text[start:end]
        css_class = f"entity-{entity_type.lower().replace('_', '-')}"
        tooltip = f"{entity_type} (Konfidenz: {score:.0%})"
        parts.append(
            f'<mark class="entity-highlight {css_class}" '
            f'title="{html.escape(tooltip)}">'
            f"{html.escape(original)}</mark>"
        )
        last_end = end

    # Escape any remaining text after the last entity
    parts.append(html.escape(text[last_end:]))

    return "".join(parts)
