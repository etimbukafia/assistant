"""
Google Gemini API provider (fallback for complex tasks)

True batching: combines multiple prompts into single API request.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from .base import BaseLLMProvider

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
    ) -> List[Dict[str, Any]]:
        """
        True batching: combines multiple prompts into single API request.
        Returns array of JSON results in same order as input prompts.
        """
        if not prompts:
            return []

        if len(prompts) == 1:
            return [self.generate(prompts[0], system_prompt)]

        self.ensure_initialized()

        # Build combined prompt
        batch_prompt = self._build_batch_prompt(prompts)

        full_system = (system_prompt or "") + (
            "\n\nYou must respond with a JSON array containing one result object for each item. "
            "Keep the same order as the input items."
        )

        try:
            if full_system:
                full_prompt = f"{full_system}\n\n{batch_prompt}"
            else:
                full_prompt = batch_prompt

            response = self.client.models.generate_content(
                model=self.config.gemini_model,
                contents=[full_prompt],
                config={
                    "response_mime_type": "application/json",
                },
            )

            # Parse the array response
            results = self._parse_batch_response(response.text, len(prompts))
            return results

        except Exception as e:
            logger.error(f"Batch generate failed: {e}")
            # Fallback: return errors for all
            return [{"_error": True, "_raw": str(e)} for _ in prompts]

    def _build_batch_prompt(self, prompts: List[str]) -> str:
        """Combine multiple prompts into a single batch prompt."""
        items = []
        for i, prompt in enumerate(prompts):
            items.append(f"=== ITEM {i + 1} ===\n{prompt}")

        combined = "\n\n".join(items)

        return f"""Process each item below and return a JSON array with one result per item.

{combined}

=== END OF ITEMS ===

Return a JSON array with {len(prompts)} objects, one for each item above, in the same order.
Example format: [{{"result": "for item 1"}}, {{"result": "for item 2"}}, ...]"""

    def _parse_batch_response(self, text: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse batch response into list of results."""
        text = text.strip()

        # Try direct parse as array
        try:
            results = json.loads(text)
            if isinstance(results, list):
                # Pad or truncate to expected count
                while len(results) < expected_count:
                    results.append({"_error": True, "_raw": "Missing result"})
                return results[:expected_count]
        except json.JSONDecodeError:
            pass

        # Try to find array in response
        import re
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                results = json.loads(match.group(0))
                if isinstance(results, list):
                    while len(results) < expected_count:
                        results.append({"_error": True, "_raw": "Missing result"})
                    return results[:expected_count]
            except json.JSONDecodeError:
                pass

        # Failed to parse - return errors
        logger.warning(f"Failed to parse batch response: {text[:200]}...")
        return [{"_error": True, "_raw": text} for _ in range(expected_count)]

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.client = None
        self._initialized = False
        logger.info("Gemini client cleaned up")
