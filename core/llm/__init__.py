"""
LLM Orchestrator - Clean provider abstraction for LLM inference.

Supports:
- Local models via HuggingFace Transformers (default: Qwen2.5-0.5B-Instruct)
- Gemini API (fallback for complex tasks)
"""

from .orchestrator import LLMOrchestrator
from .config import LLMConfig

__all__ = [
    "LLMOrchestrator",
    "LLMConfig",
]
