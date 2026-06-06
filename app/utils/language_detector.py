"""
Language detection utility.

Supports:
- Free local model via fast-langdetect (fastText based)
- Paid remote model via OpenAI API
"""

import os
import re
from typing import Optional

import httpx
from fast_langdetect import detect


# Minimum character count for reliable language detection.
# Shorter texts are returned as "und" (undetermined).
_MIN_CHARS_FOR_DETECTION = 20
_DEFAULT_CONFIDENCE_THRESHOLD = 0.60


def _detect_with_fasttext(
    text: str,
    model: str = "full",
    min_confidence: float = _DEFAULT_CONFIDENCE_THRESHOLD,
) -> str:
    """
    Detect language with fast-langdetect.

    Supported models:
    - lite: faster, smaller
    - full: higher accuracy
    """
    try:
        result = detect(text, model=model)
        lang = "und"
        score = 0.0
        if isinstance(result, list) and result:
            lang = (result[0].get("lang") or "und").lower()
            score = float(result[0].get("score", 0.0))
        elif isinstance(result, dict):
            lang = (result.get("lang") or "und").lower()
            score = float(result.get("score", 0.0))

        if score < min_confidence:
            return "und"
        return lang or "und"
    except Exception:
        return "und"


def _detect_with_openai(text: str, model: str, api_key: Optional[str], timeout: float = 20.0) -> str:
    """
    Detect language with OpenAI Chat Completions API.

    Returns ISO 639-1 lowercase language code, or "und" on failure.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        return "und"

    # Keep prompt small while preserving enough signal.
    sample = text[:4000]
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You detect document language. Return only a two-letter ISO 639-1 code "
                    "in lowercase (examples: en, fr, de, mk). If uncertain, return und."
                ),
            },
            {"role": "user", "content": sample},
        ],
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            lang = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "und")
                .strip()
                .lower()
            )
            return lang if re.fullmatch(r"[a-z]{2}|und", lang) else "und"
    except Exception:
        return "und"


def detect_language(
    text: str,
    provider: str = "fasttext",
    model: str = "full",
    min_confidence: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    api_key: Optional[str] = None,
) -> str:
    """Detect the language of the given text.

    Args:
        text: The text to detect (should be clean, extracted content).

    Returns:
        ISO 639-1 language code (e.g. ``"en"``, ``"mk"``, ``"de"``).
        Returns ``"und"`` (undetermined) when detection is not possible.
    """
    if not text or len(text.strip()) < _MIN_CHARS_FOR_DETECTION:
        return "und"

    # fast-langdetect requires newlines to be stripped.
    cleaned = re.sub(r"\n+", " ", text).strip()
    if not cleaned:
        return "und"

    provider = (provider or "fasttext").strip().lower()

    if provider in {"fasttext", "free", "local"}:
        return _detect_with_fasttext(cleaned, model=model, min_confidence=min_confidence)
    if provider in {"openai", "paid"}:
        return _detect_with_openai(cleaned, model=model, api_key=api_key)
    return "und"


def prefix_filename_with_lang(lang: str, filename: str) -> str:
    """Prepend a language code to a filename.

    Examples:
        >>> prefix_filename_with_lang("en", "about.txt")
        'en_about.txt'
        >>> prefix_filename_with_lang("und", "about.txt")
        'und_about.txt'
    """
    return f"{lang}_{filename}"
