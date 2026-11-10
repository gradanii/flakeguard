"""Create a stable digest from already-normalized failure information."""

from hashlib import sha256


def failure_signature_from_normalized(normalized_failure: str) -> str:
    """Hash normalized, sanitized failure information without persisting its contents."""
    if not normalized_failure.strip():
        raise ValueError("normalized_failure must not be empty")
    return sha256(normalized_failure.encode("utf-8")).hexdigest()
