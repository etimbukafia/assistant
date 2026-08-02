from __future__ import annotations

import hashlib


def mask_email(email: str | None) -> str:
    value = (email or "").strip().lower()
    if not value:
        return "unknown"
    if "@" not in value:
        return _mask_token(value)
    local, domain = value.split("@", 1)
    return f"{_mask_token(local)}@{domain}"


def mask_identifier(value: str | None, *, keep: int = 4) -> str:
    raw = (value or "").strip()
    if not raw:
        return "unknown"
    if len(raw) <= keep:
        return raw
    return f"{raw[:keep]}..."


def _mask_token(value: str) -> str:
    if not value:
        return "***"
    if len(value) == 1:
        return f"{value}***"
    return f"{value[0]}***{value[-1]}"


def privacy_ref(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    if not raw:
        return None
    if "@" not in raw:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"email:{digest}"
