"""
Google Gemini API provider (fallback for complex tasks)
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .base import BaseLLMProvider, JSON_INSTRUCTION, REPAIR_PROMPT

logger = logging.getLogger(__name__)

# Thread-local storage for token usage accumulation
_token_usage = threading.local()


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

    def _raw_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        *,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Internal: Generate raw text using Gemini API"""
        # Gemini uses system instruction in prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        config_kwargs: Dict[str, Any] = {}
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = int(max_output_tokens)
        if temperature is not None:
            config_kwargs["temperature"] = float(temperature)

        response = self.client.models.generate_content(
            model=self.config.gemini_model,
            contents=[full_prompt],
            config=config_kwargs or None,
        )

        # Track token usage from response
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            self._accumulate_tokens(input_tokens, output_tokens)

        return response.text.strip()

    async def _raw_agenerate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Async raw text generation using google.genai async client."""
        self.ensure_initialized()

        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        response = await self.client.aio.models.generate_content(
            model=self.config.gemini_model,
            contents=[full_prompt],
        )

        # Track token usage
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            self._accumulate_tokens(input_tokens, output_tokens)

        return response.text.strip()

    async def agenerate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_output_tokens: int = 300,
    ) -> Dict[str, Any]:
        """
        Generate with native Gemini function calling using the shared contract.
        """
        self.ensure_initialized()
        from google.genai import types as genai_types

        system_chunks: List[str] = [system_prompt] if system_prompt else []
        contents: List[genai_types.Content] = []

        for message in messages or []:
            role = (message.get("role") or "").strip().lower()
            content = message.get("content", "")

            if role == "system":
                text = str(content or "").strip()
                if text:
                    system_chunks.append(text)
                continue

            if role == "assistant":
                parts: List[genai_types.Part] = []
                text = self._stringify_content(content)
                if text:
                    parts.append(genai_types.Part.from_text(text=text))
                for function_call in message.get("function_calls", []) or []:
                    fn_payload = function_call.get("function") or {}
                    fn_name = function_call.get("name") or fn_payload.get("name")
                    fn_args = function_call.get("arguments")
                    if fn_args is None:
                        fn_args = fn_payload.get("arguments") or {}
                    if not fn_name:
                        continue
                    if not isinstance(fn_args, dict):
                        fn_args = self._parse_tool_args(fn_args)
                    parts.append(genai_types.Part.from_function_call(name=fn_name, args=fn_args))
                if parts:
                    contents.append(genai_types.Content(role="model", parts=parts))
                continue

            if role == "tool":
                tool_name = (message.get("name") or "").strip()
                if not tool_name:
                    continue
                tool_response = message.get("response") or {}
                if not isinstance(tool_response, dict):
                    tool_response = {"value": tool_response}
                contents.append(
                    genai_types.Content(
                        role="tool",
                        parts=[genai_types.Part.from_function_response(name=tool_name, response=tool_response)],
                    )
                )
                continue

            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=self._stringify_content(content))],
                )
            )

        config_kwargs: Dict[str, Any] = {
            "system_instruction": "\n\n".join(chunk for chunk in system_chunks if chunk and chunk.strip()).strip(),
            "max_output_tokens": max(64, min(int(max_output_tokens or 300), int(getattr(self.config, "api_max_output_tokens", 8192) or 8192))),
        }
        if tools:
            declarations = []
            for tool in tools:
                fn = tool.get("function", {})
                name = fn.get("name")
                if not name:
                    continue
                declarations.append(
                    genai_types.FunctionDeclaration(
                        name=name,
                        description=fn.get("description", ""),
                        parameters_json_schema=fn.get("parameters", {"type": "object", "properties": {}}),
                    )
                )
            if declarations:
                config_kwargs["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(disable=True)
                config_kwargs["tools"] = [genai_types.Tool(function_declarations=declarations)]

        response = await self.client.aio.models.generate_content(
            model=self.config.gemini_model,
            contents=contents,
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )

        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            self._accumulate_tokens(
                getattr(usage, 'prompt_token_count', 0) or 0,
                getattr(usage, 'candidates_token_count', 0) or 0,
            )

        tool_calls: List[Dict[str, Any]] = []
        for fc in list(response.function_calls or []):
            tool_calls.append(
                {
                    "id": getattr(fc, "id", None),
                    "type": "function",
                    "function": {
                        "name": fc.name,
                        "arguments": json.dumps(dict(fc.args or {}), ensure_ascii=True),
                    },
                }
            )

        return {
            "content": (response.text or "").strip(),
            "tool_calls": tool_calls,
            "usage": self.get_token_usage(),
            "stop_reason": None,
        }

    def supports_tools(self) -> bool:
        return True

    def _stringify_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if content is None:
            return ""
        return json.dumps(content, ensure_ascii=True)

    def _parse_tool_args(self, args: Any) -> Dict[str, Any]:
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"value": args}
        return {"value": args}

    def _accumulate_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token counts in thread-local storage."""
        if not hasattr(_token_usage, 'input_tokens'):
            _token_usage.input_tokens = 0
            _token_usage.output_tokens = 0
        _token_usage.input_tokens += input_tokens
        _token_usage.output_tokens += output_tokens

    def get_token_usage(self) -> Dict[str, int]:
        """Get accumulated token usage for current thread."""
        return {
            'input_tokens': getattr(_token_usage, 'input_tokens', 0),
            'output_tokens': getattr(_token_usage, 'output_tokens', 0),
            'model': self.config.gemini_model
        }

    def reset_token_usage(self) -> None:
        """Reset token usage counters for current thread."""
        _token_usage.input_tokens = 0
        _token_usage.output_tokens = 0

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
