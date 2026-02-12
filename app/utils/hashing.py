import hashlib


def hash_bytes(data: bytes) -> str:
    """
    Generate a stable hash for binary data (e.g., uploaded files).

    Useful for:
    - caching translations
    - deduplication
    - idempotency
    """
    return hashlib.sha256(data).hexdigest()
