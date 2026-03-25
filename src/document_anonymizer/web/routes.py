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
from document_anonymizer.i18n import (
    DEFAULT_LANGUAGE,
    Lang,
    get_translations,
    is_supported_lang,
    jinja_translate,
    translate,
)
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
templates.env.globals["_"] = jinja_translate

web_router = APIRouter(tags=["web"])


def _get_lang(request: Request) -> Lang:
    """Extract language preference: query param > cookie > default."""
    query_lang = request.query_params.get("lang", "")
    if is_supported_lang(query_lang):
        return query_lang
    cookie_lang = request.cookies.get("lang", "")
    if is_supported_lang(cookie_lang):
        return cookie_lang
    return DEFAULT_LANGUAGE


def _template_response(
    request: Request,
    template_name: str,
    context: dict[str, object] | None = None,
    *,
    status_code: int = 200,
) -> HTMLResponse:
    """Create a TemplateResponse with i18n context.

    Includes translations_json for client-side ``window.__t()``.
    Sets a lang cookie when the user switches language via query param.
    Escapes ``</`` → ``<\\/`` to prevent script-breakout XSS.
    """
    lang = _get_lang(request)
    ctx: dict[str, object] = {"lang": lang}
    if context:
        ctx.update(context)
    # Provide all translations as JSON for client-side window.__t().
    # Only full-page templates (extending base.html) need the JSON blob;
    # HTMX fragments inherit the already-loaded window.__translations.
    if template_name == "index.html":
        all_translations = get_translations(lang)
        ctx["translations_json"] = json.dumps(
            all_translations, ensure_ascii=False
        ).replace("</", r"<\/")
    else:
        ctx["translations_json"] = "{}"

    # Pass CSP nonce so the inline translations <script> is allowed
    csp_nonce: str = getattr(request.state, "csp_nonce", "")
    ctx["csp_nonce"] = csp_nonce

    response = templates.TemplateResponse(
        request, template_name, ctx, status_code=status_code
    )
    # Only set cookie when user explicitly requests a language via query param
    query_lang = request.query_params.get("lang", "")
    if is_supported_lang(query_lang):
        response.set_cookie(
            "lang",
            query_lang,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=365 * 24 * 3600,
        )
    return response


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


def _parse_selected_entities_json(
    json_str: str, context: str, lang: Lang = DEFAULT_LANGUAGE
) -> list[dict] | None:  # type: ignore[type-arg]
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
        raise ValueError(translate("error.entity_parse_failed", lang=lang)) from None

    if not isinstance(raw, list) or len(raw) > _MAX_SELECTED_ENTITIES:
        count = len(raw) if isinstance(raw, list) else 0
        logger.warning(f"selected_entities_{context}_bad_format", count=count)
        raise ValueError(translate("error.entity_invalid_format", lang=lang))

    return raw


def _report_skipped(
    skipped: int,
    total: int,
    accepted: int,
    context: str,
    lang: Lang = DEFAULT_LANGUAGE,
) -> None:
    """Log and raise if any items were skipped during entity reconstruction."""
    if skipped == 0:
        return
    logger.warning(
        f"selected_entities_{context}_items_skipped",
        skipped=skipped,
        total=total,
        accepted=accepted,
    )
    raise ValueError(
        translate("error.entity_skipped", lang=lang, skipped=skipped, total=total)
    )


def _reconstruct_recognizer_results(
    json_str: str, text: str, lang: Lang = DEFAULT_LANGUAGE
) -> list[RecognizerResult] | None:
    """Deserialize selected entities JSON back to Presidio RecognizerResult objects.

    Returns None only if json_str is empty (no review panel interaction).
    Raises ValueError if json_str is non-empty but malformed, so callers
    can distinguish "no selection made" from "selection corrupted".
    """
    raw = _parse_selected_entities_json(json_str, context="text", lang=lang)
    if raw is None:
        return None

    results: list[RecognizerResult] = []
    text_len = len(text)
    skipped = 0

    for item in raw:
        if not isinstance(item, dict):
            skipped += 1
            logger.debug("entity_skip_not_dict")
            continue
        try:
            start = int(item["start"])
            end = int(item["end"])
            score = float(item["score"])
            if not (0.0 <= score <= 1.0):
                skipped += 1
                logger.debug("entity_skip_score_range", score=score)
                continue
            entity_type = str(item["entity_type"])
        except (KeyError, ValueError, TypeError):
            skipped += 1
            logger.debug("entity_skip_parse_error")
            continue

        # Validate bounds
        if start < 0 or end <= start or end > text_len:
            skipped += 1
            logger.debug(
                "entity_skip_bounds",
                start=start,
                end=end,
                text_len=text_len,
            )
            continue

        # Validate entity type format (prevent XSS in CSS classes)
        if not _ENTITY_TYPE_RE.match(entity_type):
            skipped += 1
            logger.debug("entity_skip_type_format", entity_type_len=len(entity_type))
            continue

        results.append(
            RecognizerResult(
                entity_type=entity_type,
                start=start,
                end=end,
                score=score,
            )
        )

    _report_skipped(
        skipped, total=len(raw), accepted=len(results), context="text", lang=lang
    )
    return results


def _reconstruct_selected_entities_for_pdf(
    json_str: str, lang: Lang = DEFAULT_LANGUAGE
) -> list[RedactionTarget] | None:
    """Parse selected entities JSON into the format needed by redact_pdf_with_entities.

    Returns None only if json_str is empty (no review panel interaction).
    Raises ValueError if json_str is non-empty but malformed.
    """
    raw = _parse_selected_entities_json(json_str, context="pdf", lang=lang)
    if raw is None:
        return None

    targets: list[RedactionTarget] = []
    skipped = 0
    for item in raw:
        if not isinstance(item, dict) or "text" not in item:
            skipped += 1
            logger.debug("pdf_entity_skip_invalid_item")
            continue
        text = str(item["text"]).strip()
        if not text or len(text) > _MAX_ENTITY_TEXT_LENGTH:
            skipped += 1
            logger.debug(
                "pdf_entity_skip_text_validation", text_len=len(str(item["text"]))
            )
            continue
        targets.append(RedactionTarget(text=text))

    _report_skipped(
        skipped, total=len(raw), accepted=len(targets), context="pdf", lang=lang
    )
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
    return _template_response(request, "index.html", {"strategies": strategies})


_MAX_TEXT_LENGTH = 100_000


def _normalize_line_endings(text: str) -> str:
    """Normalize CRLF and CR line endings to LF.

    Browser form submissions may encode line endings as CRLF, but when text
    is later embedded in an HTML hidden input's value attribute, the HTML
    parser normalizes CRLF and CR to LF. Normalizing upfront ensures entity
    positions remain valid across the detect -> anonymize round-trip.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
    lang = _get_lang(request)
    is_pdf = False
    pdf_b64 = ""

    # Handle file upload
    if file and file.filename:
        content = await file.read()
        try:
            mime_type = validate_file_content(content, filename=file.filename)
        except FileValidationError as e:
            # error_fragment.html receives pre-translated error strings
            return _template_response(request, "error_fragment.html", {"error": str(e)})

        if mime_type == "application/pdf":
            try:
                validate_pdf_structure(content)
                text = extract_text_from_pdf(content)
            except FileValidationError as e:
                return _template_response(
                    request, "error_fragment.html", {"error": str(e)}
                )
            except PdfPageLimitExceededError as e:
                return _template_response(
                    request, "error_fragment.html", {"error": str(e)}
                )
            is_pdf = True
            pdf_b64 = base64.b64encode(content).decode()
        else:
            text = content.decode("utf-8", errors="replace")

    text = _normalize_line_endings(text)

    if not text.strip():
        return _template_response(
            request,
            "error_fragment.html",
            {"error": translate("error.no_input", lang=lang)},
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

        highlighted = _build_highlighted_text(text, entities, lang=lang)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return _template_response(
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
    except (ValueError, RuntimeError, TypeError) as exc:
        # Known NLP/Presidio processing errors (bad input, model failure)
        logger.warning("detect_form_processing_error", error=str(exc))
        request_id = getattr(request.state, "request_id", "unknown")
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.detection_failed", lang=lang, request_id=request_id
                )
            },
        )
    except Exception:
        # Unexpected error — log full traceback for investigation
        logger.exception("detect_form_unexpected_error")
        request_id = getattr(request.state, "request_id", "unknown")
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.detection_failed", lang=lang, request_id=request_id
                )
            },
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
    text = _normalize_line_endings(text)
    lang = _get_lang(request)

    try:
        strat = AnonymizationStrategy(strategy)
    except ValueError:
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.unknown_strategy",
                    lang=lang,
                    strategy=html.escape(strategy),
                )
            },
        )

    try:
        start = time.perf_counter()

        # Use pre-selected entities if provided, otherwise re-detect
        try:
            detections = _reconstruct_recognizer_results(
                selected_entities, text, lang=lang
            )
        except ValueError as e:
            return _template_response(
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
        highlighted_original = _build_highlighted_text(
            text, entities_for_highlight, lang=lang
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        return _template_response(
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
    except (ValueError, RuntimeError, TypeError) as exc:
        # Known NLP/Presidio processing errors
        logger.warning("anonymize_form_processing_error", error=str(exc))
        request_id = getattr(request.state, "request_id", "unknown")
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.anonymization_failed", lang=lang, request_id=request_id
                )
            },
        )
    except Exception:
        # Unexpected error — log full traceback for investigation
        logger.exception("anonymize_form_unexpected_error")
        request_id = getattr(request.state, "request_id", "unknown")
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.anonymization_failed", lang=lang, request_id=request_id
                )
            },
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
    lang = _get_lang(request)
    try:
        pdf_bytes = base64.b64decode(pdf_b64)
        validate_file_content(pdf_bytes)
        validate_pdf_structure(pdf_bytes)

        # Use pre-selected entities if provided
        try:
            selected = _reconstruct_selected_entities_for_pdf(
                selected_entities, lang=lang
            )
        except ValueError as e:
            return _template_response(
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
        return _template_response(
            request,
            "error_fragment.html",
            {"error": translate("error.invalid_pdf", lang=lang)},
            status_code=400,
        )
    except FileValidationError as e:
        return _template_response(
            request,
            "error_fragment.html",
            {"error": str(e)},
            status_code=400,
        )
    except PdfPageLimitExceededError as e:
        return _template_response(
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
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.incomplete_redaction",
                    lang=lang,
                    unredacted=e.unredacted_count,
                    total=e.total_count,
                ),
            },
            status_code=422,
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        # Known PDF/NLP processing errors
        logger.warning("redact_pdf_processing_error", error=str(exc))
        request_id = getattr(request.state, "request_id", "unknown")
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.pdf_redaction_failed", lang=lang, request_id=request_id
                )
            },
            status_code=500,
        )
    except Exception:
        # Unexpected error — log full traceback for investigation
        logger.exception("redact_pdf_unexpected_error")
        request_id = getattr(request.state, "request_id", "unknown")
        return _template_response(
            request,
            "error_fragment.html",
            {
                "error": translate(
                    "error.pdf_redaction_failed", lang=lang, request_id=request_id
                )
            },
            status_code=500,
        )

    return Response(
        content=redacted_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=redacted.pdf"},
    )


def _build_highlighted_text(
    text: str,
    entities: list[_EntityHighlight],
    lang: Lang = DEFAULT_LANGUAGE,
) -> str:
    """Build HTML with color-coded PII highlights.

    Walks through the text segment by segment, escaping non-entity gaps
    and entity content individually, then wrapping entities in <mark> tags.
    Overlapping entities are skipped (earliest start position wins; for ties,
    the longest span wins).
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
        confidence = translate("common.confidence", lang=lang, score=f"{score:.0%}")
        tooltip = f"{html.escape(entity_type)} ({html.escape(confidence)})"
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
