"""
LLM Orchestrator - Clean provider selection and inference.

Abstracts away which LLM handles a task (local Qwen vs Gemini API).
All output is structured JSON.
"""
import logging
from typing import Any, Dict, List, Optional

from .config import LLMConfig
from .providers.base import BaseLLMProvider
from .providers.hf_transformers import HFTransformersProvider
from .providers.gemini import GeminiProvider
from .providers.anthropic import AnthropicProvider

logger = logging.getLogger(__name__)


class LLMOrchestrator:
    """
    Simple LLM provider orchestration.

    All methods return structured JSON (Dict or List[Dict]).
    Free text is wrapped in JSON fields by prompts.

    Usage:
        orchestrator = LLMOrchestrator()
        result = orchestrator.generate("Summarize: ... Return {summary: str}")
        results = orchestrator.generate_batch([prompt1, prompt2])
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        self._provider: Optional[BaseLLMProvider] = None

    @property
    def provider(self) -> BaseLLMProvider:
        """Lazy-load the configured provider"""
        if self._provider is None:
            self._provider = self._create_provider()
        return self._provider

    def _create_provider(self) -> BaseLLMProvider:
        """Create provider based on config"""
        if self.config.provider == "huggingface":
            logger.info(f"Using local model: {self.config.hf_model_id}")
            return HFTransformersProvider(self.config)
        elif self.config.provider == "gemini":
            logger.info(f"Using Gemini API: {self.config.gemini_model}")
            return GeminiProvider(self.config)
        elif self.config.provider == "anthropic":
            logger.info(f"Using Anthropic API: {self.config.anthropic_model}")
            return AnthropicProvider(self.config)
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.

        Args:
            prompt: User prompt (should specify expected JSON keys)
            system_prompt: Optional system instructions

        Returns:
            Parsed JSON dict. On failure: {"_error": True, "_raw": "..."}
        """
        return self.provider.generate(prompt, system_prompt)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        *,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate raw text synchronously."""
        return self.provider.generate_text(
            prompt,
            system_prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    async def agenerate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Async generate raw text (no JSON parsing).

        For chat/conversational use where the response is natural language.
        Uses native async I/O when the provider supports it (e.g. Gemini).
        """
        return await self.provider.agenerate_text(prompt, system_prompt)

    async def agenerate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_output_tokens: int = 300,
    ) -> Dict[str, Any]:
        """
        Async generate with normalized tool calling.

        Providers with native tool support adapt their SDK-specific message and
        tool formats behind the shared interface.
        """
        return await self.provider.agenerate_with_tools(
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            max_output_tokens=max_output_tokens,
        )

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured JSON responses for multiple prompts.

        Args:
            prompts: List of user prompts
            system_prompt: Optional system instructions (applied to all)

        Returns:
            List of parsed JSON dicts in same order as input
        """
        return self.provider.generate_batch(prompts, system_prompt)

    def switch_provider(self, provider: str) -> None:
        """Switch to a different provider at runtime"""
        if provider not in ("huggingface", "gemini", "anthropic"):
            raise ValueError(f"Unknown provider: {provider}")

        if self._provider is not None:
            self._provider.cleanup()
            self._provider = None

        self.config.provider = provider
        logger.info(f"Switched to provider: {provider}")

    def supports_tools(self) -> bool:
        """Whether the active provider supports native tool calling."""
        return self.provider.supports_tools()

    def cleanup(self) -> None:
        """Release resources"""
        if self._provider is not None:
            self._provider.cleanup()
            self._provider = None

    def get_token_usage(self) -> Dict[str, Any]:
        """Get accumulated token usage from current provider."""
        if self._provider is not None:
            return self._provider.get_token_usage()
        return {'input_tokens': 0, 'output_tokens': 0, 'model': 'unknown'}

    def reset_token_usage(self) -> None:
        """Reset token usage counters."""
        if self._provider is not None:
            self._provider.reset_token_usage()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
