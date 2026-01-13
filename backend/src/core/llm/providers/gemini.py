"""
Google Gemini API provider (fallback for complex tasks)
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .base import BaseLLMProvider, JSON_INSTRUCTION, REPAIR_PROMPT

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API provider.

    Gemini 2.5 Flash:
    - 1M token context (practical 128-200K)
    - Fast, cost-effective
    - Good at structured output
    """

    def __init__(self, config: Any):
        super().__init__(config)
        self.client = None

    def initialize(self) -> None:
        """Initialize Gemini client"""
        try:
            import google.genai as genai
        except ImportError as e:
            raise ImportError(
                "google-genai required. Install with: pip install google-genai"
            ) from e

        api_key = self.config.gemini_api_key
        if not api_key:
            # Try to get from environment
            import os
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "Gemini API key required. Set GOOGLE_API_KEY or GEMINI_API_KEY env var."
            )

        self.client = genai.Client(api_key=api_key)
        self._initialized = True
        logger.info(f"Gemini client initialized with model: {self.config.gemini_model}")

    def _raw_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Internal: Generate raw text using Gemini API"""
        # Gemini uses system instruction in prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        response = self.client.models.generate_content(
            model=self.config.gemini_model,
            contents=[full_prompt],
        )

        return response.text.strip()

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        max_workers: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured JSON for multiple prompts using concurrent API calls.
        Uses base class generate() which includes retry logic.
        """
        if not prompts:
            return []

        if len(prompts) == 1:
            return [self.generate(prompts[0], system_prompt)]

        self.ensure_initialized()
        results = [None] * len(prompts)

        def generate_one(idx: int, prompt: str) -> tuple:
            # Uses base class generate() with retry logic
            response = self.generate(prompt, system_prompt)
            return idx, response

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(generate_one, i, p): i
                for i, p in enumerate(prompts)
            }
            for future in as_completed(futures):
                try:
                    idx, response = future.result()
                    results[idx] = response
                except Exception as e:
                    idx = futures[future]
                    logger.error(f"Batch generate error for prompt {idx}: {e}")
                    results[idx] = {"_error": True, "_raw": str(e)}

        return results

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.client = None
        self._initialized = False
        logger.info("Gemini client cleaned up")
