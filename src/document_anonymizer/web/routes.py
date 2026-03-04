"""Web frontend routes serving Jinja2 templates."""

import base64
import binascii
import html
import json
import re
import time
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.api.dependencies import get_analyzer, get_anonymizer
from document_anonymizer.document.pdf_handler import (
    IncompleteRedactionError,
    PdfPageLimitExceededError,
    RedactionTarget,
    extract_text_from_pdf,
    redact_pdf,
    redact_pdf_with_entities,
)
from document_anonymizer.document.text_handler import detect_pii_in_text
from document_anonymizer.security.validation import (
    FileValidationError,
    validate_file_content,
    validate_pdf_structure,
)

logger = structlog.get_logger(__name__)


Tier = Literal["high", "medium", "low"]

# Uppercase letters, digits, underscores only (max 50; blocks XSS in CSS classes)
_ENTITY_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,49}$")


class _EntityHighlight(TypedDict):
    entity_type: str
    start: int
    end: int
    score: float
    text: str
    index: int
    tier: Tier


_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

web_router = APIRouter(tags=["web"])


def _score_to_tier(score: float) -> Tier:
    """Map a confidence score to a review tier."""
    if score >= 0.7:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _make_entity_highlight(
    entity_type: str,
    start: int,
    end: int,
    score: float,
    text: str,
    index: int,
) -> _EntityHighlight:
    """Create an _EntityHighlight with tier derived from score."""
    return {
        "entity_type": entity_type,
        "start": start,
        "end": end,
        "score": round(score, 3),
        "text": text,
        "index": index,
        "tier": _score_to_tier(score),
    }


def _group_entities_by_tier(
    entities: list[_EntityHighlight],
) -> dict[Tier, list[_EntityHighlight]]:
    """Group entities into tier buckets for the review panel."""
    groups: dict[Tier, list[_EntityHighlight]] = {
        "high": [],
        "medium": [],
        "low": [],
    }
    for entity in entities:
        groups[entity["tier"]].append(entity)
    return groups


_MAX_SELECTED_ENTITIES = 500
_MAX_ENTITY_TEXT_LENGTH = 1000


def _parse_selected_entities_json(json_str: str, context: str) -> list[dict] | None:  # type: ignore[type-arg]
    """Parse and validate the shared JSON envelope for selected entities.

    Returns None if json_str is empty (no review panel interaction).
    Raises ValueError if json_str is non-empty but malformed.
    """
    if not json_str.strip():
        return None

    try:
        raw = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"selected_entities_{context}_invalid_json")
        msg = "Entitätsauswahl konnte nicht verarbeitet werden."
        raise ValueError(msg) from None

    if not isinstance(raw, list) or len(raw) > _MAX_SELECTED_ENTITIES:
        count = len(raw) if isinstance(raw, list) else 0
        logger.warning(f"selected_entities_{context}_bad_format", count=count)
        msg = "Entitätsauswahl hat ein ungültiges Format."
        raise ValueError(msg)

    return raw


def _report_skipped(skipped: int, total: int, accepted: int, context: str) -> None:
    """Log and raise if any items were skipped during entity reconstruction."""
    if skipped == 0:
        return
    logger.warning(
        f"selected_entities_{context}_items_skipped",
        skipped=skipped,
        total=total,
        accepted=accepted,
    )
    msg = (
        f"{skipped} von {total} ausgewählten Entitäten konnten nicht "
        f"verarbeitet werden. Bitte erneut versuchen."
    )
    raise ValueError(msg)


def _reconstruct_recognizer_results(
    json_str: str, text: str
) -> list[RecognizerResult] | None:
    """Deserialize selected entities JSON back to Presidio RecognizerResult objects.

    Returns None only if json_str is empty (no review panel interaction).
    Raises ValueError if json_str is non-empty but malformed, so callers
    can distinguish "no selection made" from "selection corrupted".
    """
    raw = _parse_selected_entities_json(json_str, context="text")
    if raw is None:
        return None

    results: list[RecognizerResult] = []
    text_len = len(text)
    skipped = 0

    for item in raw:
        if not isinstance(item, dict):
            skipped += 1
            continue
        try:
            start = int(item["start"])
            end = int(item["end"])
            score = float(item["score"])
            entity_type = str(item["entity_type"])
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue

        # Validate bounds
        if start < 0 or end <= start or end > text_len:
            skipped += 1
            continue

        # Validate entity type format (prevent XSS in CSS classes)
        if not _ENTITY_TYPE_RE.match(entity_type):
            skipped += 1
            continue

        results.append(
            RecognizerResult(
                entity_type=entity_type,
                start=start,
                end=end,
                score=score,
            )
        )

    _report_skipped(skipped, total=len(raw), accepted=len(results), context="text")
    return results


def _reconstruct_selected_entities_for_pdf(
    json_str: str,
) -> list[RedactionTarget] | None:
    """Parse selected entities JSON into the format needed by redact_pdf_with_entities.

    Returns None only if json_str is empty (no review panel interaction).
    Raises ValueError if json_str is non-empty but malformed.
    """
    raw = _parse_selected_entities_json(json_str, context="pdf")
    if raw is None:
        return None

    targets: list[RedactionTarget] = []
    skipped = 0
    for item in raw:
        if not isinstance(item, dict) or "text" not in item:
            skipped += 1
            continue
        text = str(item["text"]).strip()
        if not text or len(text) > _MAX_ENTITY_TEXT_LENGTH:
            skipped += 1
            continue
        targets.append(RedactionTarget(text=text))

    _report_skipped(skipped, total=len(raw), accepted=len(targets), context="pdf")
    return targets


async def _require_htmx_header(request: Request) -> None:
    """CSRF protection: require HX-Request header on POST endpoints.

    HTMX sends this header automatically. Cross-origin forms cannot set
    custom headers, so this blocks CSRF attacks without needing tokens.
    Only used as a dependency on POST routes.
    """
    if not request.headers.get("HX-Request"):
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
                text = extract_text_from_pdf(content)
            except FileValidationError as e:
                return templates.TemplateResponse(
                    request, "error_fragment.html", {"error": str(e)}
                )
            except PdfPageLimitExceededError as e:
                return templates.TemplateResponse(
                    request, "error_fragment.html", {"error": str(e)}
                )
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

        # Sort consistently: by start position, longest span first
        sorted_results = sorted(results, key=lambda r: (r.start, -r.end))

        entities: list[_EntityHighlight] = [
            _make_entity_highlight(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=r.score,
                text=text[r.start : r.end],
                index=idx,
            )
            for idx, r in enumerate(sorted_results)
        ]

        entities_by_tier = _group_entities_by_tier(entities)

        # Serialize entity data for the embedded JSON block.
        # Replace </ with <\/ to prevent </script> breakout (XSS).
        entities_json = json.dumps(entities, ensure_ascii=False).replace("</", r"<\/")

        highlighted = _build_highlighted_text(text, entities)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return templates.TemplateResponse(
            request,
            "results.html",
            {
                "entities": entities,
                "entities_by_tier": entities_by_tier,
                "entities_json": entities_json,
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
        request_id = getattr(request.state, "request_id", "unknown")
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": f"Fehler bei der PII-Erkennung. (Referenz: {request_id})"},
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
    selected_entities: str = Form(default=""),
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

        # Use pre-selected entities if provided, otherwise re-detect
        try:
            detections = _reconstruct_recognizer_results(selected_entities, text)
        except ValueError as e:
            return templates.TemplateResponse(
                request,
                "error_fragment.html",
                {"error": str(e)},
            )

        if detections is None:
            detections = detect_pii_in_text(
                analyzer, text, score_threshold=score_threshold
            )

        anonymized = anonymize_text(anonymizer, text, detections, strategy=strat)

        sorted_detections = sorted(detections, key=lambda r: (r.start, -r.end))
        entities_for_highlight: list[_EntityHighlight] = [
            _make_entity_highlight(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=r.score,
                text=text[r.start : r.end],
                index=idx,
            )
            for idx, r in enumerate(sorted_detections)
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
                "selected_entities": selected_entities,
            },
        )
    except Exception:
        logger.exception("anonymize_form_error")
        request_id = getattr(request.state, "request_id", "unknown")
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": f"Fehler bei der Anonymisierung. (Referenz: {request_id})"},
        )


@web_router.post("/redact-pdf", dependencies=[Depends(_require_htmx_header)])
async def redact_pdf_form(
    request: Request,
    pdf_b64: str = Form(...),
    score_threshold: Annotated[float, Form(ge=0.0, le=1.0)] = 0.35,
    selected_entities: str = Form(default=""),
    analyzer: AnalyzerEngine = Depends(get_analyzer),  # noqa: B008
) -> Response:
    """Handle PDF redaction — returns redacted PDF for download."""
    try:
        pdf_bytes = base64.b64decode(pdf_b64)
        validate_file_content(pdf_bytes)
        validate_pdf_structure(pdf_bytes)

        # Use pre-selected entities if provided
        try:
            selected = _reconstruct_selected_entities_for_pdf(selected_entities)
        except ValueError as e:
            return templates.TemplateResponse(
                request,
                "error_fragment.html",
                {"error": str(e)},
                status_code=400,
            )

        if selected is not None:
            redacted_bytes, _ = redact_pdf_with_entities(pdf_bytes, selected)
        else:
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
    except PdfPageLimitExceededError as e:
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": str(e)},
            status_code=400,
        )
    except IncompleteRedactionError as e:
        logger.warning(
            "incomplete_redaction",
            unredacted=e.unredacted_count,
            total=e.total_count,
        )
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
        request_id = getattr(request.state, "request_id", "unknown")
        return templates.TemplateResponse(
            request,
            "error_fragment.html",
            {"error": f"PDF-Schwärzung fehlgeschlagen. (Referenz: {request_id})"},
            status_code=500,
        )

    return Response(
        content=redacted_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=redacted.pdf"},
    )


def _build_highlighted_text(text: str, entities: list[_EntityHighlight]) -> str:
    """Build HTML with color-coded PII highlights.

    Walks through the text segment by segment, escaping non-entity gaps
    and entity content individually, then wrapping entities in <mark> tags.
    Overlapping entities are skipped (the first span by start position wins).
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
        entity_index = entity["index"]
        tier = entity["tier"]

        # Escape the gap between the last entity and this one
        parts.append(html.escape(text[last_end:start]))

        # Build the <mark> tag with escaped content
        original = text[start:end]
        safe_type = html.escape(entity_type.lower().replace("_", "-"))
        css_class = f"entity-{safe_type}"
        tooltip = f"{html.escape(entity_type)} (Konfidenz: {score:.0%})"
        parts.append(
            f'<mark class="entity-highlight {css_class}" '
            f'data-entity-index="{int(entity_index)}" '
            f'data-tier="{html.escape(tier)}" '
            f'title="{tooltip}">'
            f"{html.escape(original)}</mark>"
        )
        last_end = end

    # Escape any remaining text after the last entity
    parts.append(html.escape(text[last_end:]))

    return "".join(parts)
