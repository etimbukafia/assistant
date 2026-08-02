"""Singleton Google GenAI client for chat/tool function-calling."""

from __future__ import annotations

import threading
from typing import Optional

import google.genai as genai

from app.infra.config import get_settings


_lock = threading.Lock()
_client: Optional[genai.Client] = None


def get_genai_client() -> Optional[genai.Client]:
    """Return a shared client instance for this process."""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    api_key = (settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY or "").strip()
    if not api_key:
        return None

    with _lock:
        if _client is None:
            _client = genai.Client(api_key=api_key)
    return _client
