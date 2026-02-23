"""GenAI client helper for playground (singleton)."""

import os
from typing import Optional
from dotenv import load_dotenv

import google.genai as genai

load_dotenv()

_client: Optional[genai.Client] = None


def get_client() -> Optional[genai.Client]:
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    _client = genai.Client(api_key=api_key)
    return _client


def get_genai_client() -> Optional[genai.Client]:
    """Compatibility alias with main backend imports."""
    return get_client()
