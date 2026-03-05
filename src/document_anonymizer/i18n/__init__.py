"""Internationalization support for the web UI."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeGuard, get_args

if TYPE_CHECKING:
    from collections.abc import Mapping

import structlog
from jinja2 import pass_context

logger = structlog.get_logger(__name__)

Lang = Literal["de", "en"]
SUPPORTED_LANGUAGES: set[str] = {"de", "en"}
DEFAULT_LANGUAGE: Lang = "de"

# Ensure Lang type and SUPPORTED_LANGUAGES stay in sync
if set(get_args(Lang)) != SUPPORTED_LANGUAGES:  # pragma: no cover
    msg = "Lang type and SUPPORTED_LANGUAGES are out of sync"
    raise RuntimeError(msg)

_TRANSLATIONS_DIR = Path(__file__).parent / "translations"


def is_supported_lang(value: str) -> TypeGuard[Lang]:
    """Check if a string is a supported language code (narrows type to Lang)."""
    return value in SUPPORTED_LANGUAGES


def _load_translations(lang: str) -> dict[str, str]:
    """Normalize unsupported lang codes to default, return cached."""
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return _load_translations_cached(lang)


@lru_cache(maxsize=2)  # maxsize matches len(SUPPORTED_LANGUAGES)
def _load_translations_cached(lang: str) -> dict[str, str]:
    """Load and cache a translation file."""
    path = _TRANSLATIONS_DIR / f"{lang}.json"
    try:
        with path.open(encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        logger.exception("translation_file_load_failed", lang=lang)
        return {}
    return data


def get_translations(lang: str) -> dict[str, str]:
    """Get all translations for a language (public API)."""
    return _load_translations(lang)


def translate(
    key: str, lang: Lang = DEFAULT_LANGUAGE, **kwargs: str | int | float
) -> str:
    """Look up a translation key and interpolate any kwargs."""
    translations = _load_translations(lang)
    template = translations.get(key)
    if template is None:
        logger.warning("translation_key_missing", key=key, lang=lang)
        return key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            logger.warning("translation_format_error", key=key, lang=lang)
            return template
    return template


@pass_context
def jinja_translate(
    context: Mapping[str, Any], key: str, **kwargs: str | int | float
) -> str:
    """Jinja2 global function: {{ _("key", arg=val) }}.

    The @pass_context decorator injects a jinja2.runtime.Context (Mapping-like).
    """
    raw_lang = context.get("lang", DEFAULT_LANGUAGE)
    lang = raw_lang if is_supported_lang(raw_lang) else DEFAULT_LANGUAGE
    return translate(key, lang=lang, **kwargs)
