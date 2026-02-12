SUPPORTED_LANGUAGES = {
    "english",
    "french",
    "german",
    "spanish",
    "italian",
    "portuguese",
    "hindi",
    "japanese",
    "chinese",
}

def normalize_language(lang: str) -> str:
    """
    Normalize user-provided language input.
    """
    return lang.strip().lower()


def is_supported_language(lang: str) -> bool:
    return normalize_language(lang) in SUPPORTED_LANGUAGES
