"""
Anthropic Claude API provider.
"""
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

_token_usage = threading.local()


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic API provider.

    Uses the Messages API for raw text, structured prompts, and native tool use.
    """

    def __init__(self, config: Any):
        super().__init__(config)
        self.client = None
        self.async_client = None

    def initialize(self) -> None:
        """Initialize Anthropic clients."""
        try:
            from anthropic import Anthropic, AsyncAnthropic
        except ImportError as e:
            raise ImportError(
                "anthropic required. Install with: pip install anthropic"
            ) from e

        api_key = self.config.anthropic_api_key
        if not api_key:
            import os
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY.")

        self.client = Anthropic(api_key=api_key)
        self.async_client = AsyncAnthropic(api_key=api_key)
        self._initialized = True
        logger.info("Anthropic client initialized with model: %s", self.config.anthropic_model)

    def _raw_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        *,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Internal: Generate raw text using Anthropic Messages API."""
        self.ensure_initialized()
        request_kwargs: Dict[str, Any] = {
            "model": self.config.anthropic_model,
            "max_tokens": int(max_output_tokens or self._max_output_tokens()),
            "system": system_prompt or "",
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            request_kwargs["temperature"] = float(temperature)
        response = self.client.messages.create(
            **request_kwargs,
        )
        self._accumulate_usage(response)
        return self._extract_text(response)

    async def _raw_agenerate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Async raw text generation using Anthropic Async client."""
        self.ensure_initialized()
        response = await self.async_client.messages.create(
            model=self.config.anthropic_model,
            max_tokens=self._max_output_tokens(),
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )
        self._accumulate_usage(response)
        return self._extract_text(response)

    async def agenerate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_output_tokens: int = 300,
    ) -> Dict[str, Any]:
        """
        Generate with native Claude tool use.

        The normalized return shape matches the existing chat contract:
        {
            "content": str,
            "tool_calls": [{"id": str, "function": {"name": str, "arguments": str}}],
            "usage": {"input_tokens": int, "output_tokens": int, "model": str},
            "stop_reason": str,
        }
        """
        self.ensure_initialized()
        merged_system, anthropic_messages = self._to_anthropic_messages(messages, system_prompt=system_prompt)
        request_kwargs: Dict[str, Any] = {
            "model": self.config.anthropic_model,
            "max_tokens": max(64, min(int(max_output_tokens or 300), self._max_output_tokens())),
            "messages": anthropic_messages,
        }
        if merged_system:
            request_kwargs["system"] = merged_system
        anthropic_tools = self._to_anthropic_tools(tools or [])
        if anthropic_tools:
            request_kwargs["tools"] = anthropic_tools

        response = await self.async_client.messages.create(**request_kwargs)
        self._accumulate_usage(response)

        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for block in getattr(response, "content", []) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_value = getattr(block, "text", "") or ""
                if text_value:
                    text_parts.append(text_value)
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", None),
                        "type": "function",
                        "function": {
                            "name": getattr(block, "name", ""),
                            "arguments": json.dumps(getattr(block, "input", {}) or {}, ensure_ascii=True),
                        },
                    }
                )

        usage = self.get_token_usage()
        return {
            "content": "\n".join(part.strip() for part in text_parts if part.strip()).strip(),
            "tool_calls": tool_calls,
            "usage": usage,
            "stop_reason": getattr(response, "stop_reason", None),
        }

    def supports_tools(self) -> bool:
        return True

    def _max_output_tokens(self) -> int:
        return max(64, int(getattr(self.config, "api_max_output_tokens", 8192) or 8192))

    def _extract_text(self, response: Any) -> str:
        parts: List[str] = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text_value = getattr(block, "text", "") or ""
                if text_value:
                    parts.append(text_value)
        return "\n".join(part.strip() for part in parts if part.strip()).strip()

    def _accumulate_usage(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        if not hasattr(_token_usage, "input_tokens"):
            _token_usage.input_tokens = 0
            _token_usage.output_tokens = 0
        _token_usage.input_tokens += input_tokens
        _token_usage.output_tokens += output_tokens

    def _to_anthropic_messages(
        self,
        messages: List[Dict[str, Any]],
        *,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        system_chunks: List[str] = [system_prompt] if system_prompt else []
        anthropic_messages: List[Dict[str, Any]] = []

        for message in messages or []:
            role = (message.get("role") or "").strip().lower()
            content = message.get("content", "")

            if role == "system":
                text = str(content or "").strip()
                if text:
                    system_chunks.append(text)
                continue

            if role == "assistant":
                parts: List[Dict[str, Any]] = []
                text = self._stringify_content(content)
                if text:
                    parts.append({"type": "text", "text": text})
                for function_call in message.get("function_calls", []) or []:
                    fn_id = function_call.get("id") or function_call.get("tool_call_id") or function_call.get("call_id")
                    function_payload = function_call.get("function") or {}
                    fn_name = function_call.get("name") or function_payload.get("name")
                    fn_args = function_call.get("arguments")
                    if fn_args is None:
                        fn_args = function_payload.get("arguments") or {}
                    if not fn_name:
                        continue
                    if not isinstance(fn_args, dict):
                        fn_args = self._parse_tool_args(fn_args)
                    parts.append(
                        {
                            "type": "tool_use",
                            "id": fn_id or f"toolu_{fn_name}",
                            "name": fn_name,
                            "input": fn_args,
                        }
                    )
                anthropic_messages.append({"role": "assistant", "content": parts or [{"type": "text", "text": ""}]})
                continue

            if role == "tool":
                tool_response = message.get("response") or {}
                if not isinstance(tool_response, dict):
                    tool_response = {"value": tool_response}
                tool_call_id = (
                    message.get("tool_call_id")
                    or message.get("id")
                    or message.get("tool_use_id")
                    or f"toolu_{message.get('name', 'unknown')}"
                )
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": json.dumps(tool_response, ensure_ascii=True),
                            }
                        ],
                    }
                )
                continue

            anthropic_messages.append(
                {
                    "role": "user",
                    "content": self._stringify_content(content),
                }
            )

        merged_system = "\n\n".join(chunk.strip() for chunk in system_chunks if chunk and chunk.strip()).strip()
        return merged_system, anthropic_messages

    def _to_anthropic_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted_tools: List[Dict[str, Any]] = []
        for tool in tools or []:
            fn = tool.get("function", {})
            name = fn.get("name")
            if not name:
                continue
            formatted_tools.append(
                {
                    "name": name,
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return formatted_tools

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

    def get_token_usage(self) -> Dict[str, Any]:
        return {
            "input_tokens": getattr(_token_usage, "input_tokens", 0),
            "output_tokens": getattr(_token_usage, "output_tokens", 0),
            "model": self.config.anthropic_model,
        }

    def reset_token_usage(self) -> None:
        _token_usage.input_tokens = 0
        _token_usage.output_tokens = 0

    def cleanup(self) -> None:
        self.client = None
        self.async_client = None
        self._initialized = False
        logger.info("Anthropic client cleaned up")
