"""
Language detection and translation helpers used to make Nyaya Sahayak
work across English, Hindi and Kannada (and, incidentally, any other
language langdetect/GoogleTranslator support).
"""
from langdetect import DetectorFactory, detect
from deep_translator import GoogleTranslator

# Make langdetect deterministic across calls.
DetectorFactory.seed = 0

_SUPPORTED_LANGUAGES = {"en", "hi", "kn"}

_LANGDETECT_TO_SUPPORTED = {
    "en": "en",
    "hi": "hi",
    "kn": "kn",
}


def detect_language(text: str) -> str:
    """
    Returns a language code: 'en', 'hi', 'kn', or whatever langdetect
    reports for languages outside our primary supported set.
    """
    if not text or not text.strip():
        return "en"
    try:
        code = detect(text)
    except Exception:
        return "en"
    return _LANGDETECT_TO_SUPPORTED.get(code, code)


def translate_to_english(text: str, source_lang: str) -> str:
    """Translate `text` from `source_lang` to English. No-op if already English."""
    if not text or not text.strip():
        return text
    if source_lang == "en":
        return text
    try:
        return GoogleTranslator(source=source_lang, target="en").translate(text)
    except Exception:
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    """Translate `text` from English to `target_lang`. No-op if target is English."""
    if not text or not text.strip():
        return text
    if target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except Exception:
        return text
