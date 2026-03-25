"""Shared constants for confidence scoring and detection thresholds."""

__all__ = [
    "DEFAULT_SCORE_THRESHOLD",
    "RECOGNIZER_BASE_SCORE_HIGH",
    "RECOGNIZER_BASE_SCORE_LOW",
    "TIER_HIGH_THRESHOLD",
    "TIER_MEDIUM_THRESHOLD",
]

# Minimum confidence score for a detection to be included in results.
# Lower values catch more entities but increase false positives.
DEFAULT_SCORE_THRESHOLD = 0.35

# Tier boundaries for the entity review panel.
# High-confidence entities (>= TIER_HIGH_THRESHOLD) are shown expanded by default.
TIER_HIGH_THRESHOLD = 0.7
TIER_MEDIUM_THRESHOLD = 0.5

# Base confidence scores for pattern-based recognizers.
# Higher base = more confident the pattern alone is a real match.
# Context words boost these scores at runtime.
RECOGNIZER_BASE_SCORE_HIGH = 0.5
RECOGNIZER_BASE_SCORE_LOW = 0.3
