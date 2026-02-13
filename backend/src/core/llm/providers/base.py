"""
Abstract base class for LLM providers.

Design principles:
- Single interface: generate() always returns Dict[str, Any]
- Schema-first: pass Pydantic schema for guaranteed structure
- Constrained decoding (Outlines) for local models
- Fallback repair for providers without schema support
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
import json
import re
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Standard JSON instruction appended to system prompts
JSON_INSTRUCTION = (
    "\n\nRespond with valid JSON. Use the exact keys specified in the prompt. "
    "Keep structure shallow. No markdown wrapping needed."
)

REPAIR_PROMPT = (
    "Your previous response was not valid JSON. "
    "Please respond with ONLY valid JSON matching the requested schema. "
    "Previous response:\n{raw}\n\nTry again:"
)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All output is structured JSON. Free text is wrapped in JSON fields.
    Includes validation and retry logic for small model reliability.
    """

    def __init__(self, config: Any):
        self.config = config
        self._initialized = False
        self.max_retries = 2

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the provider (load model, setup client, etc.)
        Called lazily on first use.
        """
        pass

    @abstractmethod
    def _raw_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Internal: Generate raw text from model.
        Subclasses implement this. Not exposed publicly.
        """
        pass

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: User prompt (should specify expected JSON keys)
            system_prompt: Optional system instructions
            schema: Optional Pydantic model for output validation.
                    HFOutlinesProvider uses this for constrained decoding.
                    Other providers use it for post-validation.

        Returns:
            Parsed JSON dict. On unrecoverable failure:
            {"_error": True, "_raw": "..."}
        """
        self.ensure_initialized()

        # Default implementation: JSON instruction + repair + optional validation
        # Subclasses (HFOutlinesProvider) override for constrained decoding
        full_system = (system_prompt or "") + JSON_INSTRUCTION

        for attempt in range(self.max_retries):
            raw = self._raw_generate(prompt, full_system)
            result = self._parse_json(raw)

            if "_error" not in result:
                # Post-validate against schema if provided
                if schema is not None:
                    validated = self._validate_schema(result, schema)
                    if validated is not None:
                        return validated
                    # Validation failed, retry
                    logger.warning(f"Schema validation failed (attempt {attempt + 1}), retrying...")
                    prompt = REPAIR_PROMPT.format(raw=raw[:500])
                    continue
                return result

            if attempt < self.max_retries - 1:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}), retrying...")
                prompt = REPAIR_PROMPT.format(raw=raw[:500])

        logger.error(f"JSON parse failed after {self.max_retries} attempts")
        return {"_error": True, "_raw": raw}

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured JSON for multiple prompts.

        Args:
            prompts: List of user prompts
            system_prompt: Optional system instructions (applied to all)
            schema: Optional Pydantic model for output validation

        Default: sequential calls. Subclasses may override for true batching.
        """
        return [self.generate(p, system_prompt, schema) for p in prompts]

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from model output with multiple fallback strategies.
        Always returns a dict - bare arrays are wrapped.
        """
        text = text.strip()

        # Pre-process: Fix malformed unicode escapes (e.g., \u without 4 hex digits)
        # This handles cases like "C:\users" which creates invalid \u escape
        text = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', text)

        # Strategy 1: Direct parse
        try:
            result = json.loads(text)
            return self._ensure_dict(result)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                return self._ensure_dict(result)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON object/array pattern
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            try:
                result = json.loads(match.group(1))
                return self._ensure_dict(result)
            except json.JSONDecodeError:
                pass

        # Strategy 4: Try to fix common issues
        fixed = self._attempt_json_repair(text)
        if fixed:
            return fixed

        return {"_error": True, "_raw": text}

    def _ensure_dict(self, result: Any) -> Dict[str, Any]:
        """Ensure result is a dict - wrap bare arrays with guessed key."""
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            # Guess the key based on content
            for key in ['tasks', 'dates', 'people', 'decisions', 'items', 'results']:
                return {key: result}
        # Scalar value - wrap in generic key
        return {"value": result}

    def _validate_schema(self, data: Dict[str, Any], schema: Type[BaseModel]) -> Optional[Dict[str, Any]]:
        """
        Validate parsed JSON against Pydantic schema.

        Returns:
            Validated dict on success, None on validation failure.
        """
        try:
            validated = schema.model_validate(data)
            return validated.model_dump()
        except Exception as e:
            logger.warning(f"Schema validation failed: {e}")
            return None

    def _attempt_json_repair(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to repair common JSON issues from small models.
        """
        # Strategy 0: Fix malformed unicode escapes (e.g., \u without 4 hex digits)
        # This handles cases like "C:\users" which creates invalid \u escape
        def fix_unicode_escapes(s: str) -> str:
            # Replace \u not followed by 4 hex digits with \\u (escaped backslash)
            return re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', s)

        text = fix_unicode_escapes(text)

        # Strategy 1: Remove trailing commas
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Add missing closing braces
        if text.count("{") > text.count("}"):
            try:
                return json.loads(text + "}" * (text.count("{") - text.count("}")))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Fix unescaped newlines/special chars in JSON string values
        # Find string values and properly escape them
        try:
            # Pattern: "key": "value with
            # newlines" - capture the value part
            def fix_json_string(m):
                prefix = m.group(1)  # "key": "
                content = m.group(2)  # the string content
                suffix = m.group(3)  # closing "
                # Escape special chars
                escaped = (content
                    .replace('\\', '\\\\')  # escape backslashes first
                    .replace('\n', '\\n')
                    .replace('\r', '\\r')
                    .replace('\t', '\\t')
                    .replace('"', '\\"'))
                return f'{prefix}{escaped}{suffix}'

            # Match "key": "...content..." patterns, allowing newlines in content
            fixed = re.sub(
                r'("[\w]+"\s*:\s*")([^"]*?)(")',
                fix_json_string,
                text,
                flags=re.DOTALL
            )
            result = json.loads(fixed)
            return result
        except (json.JSONDecodeError, re.error):
            pass

        # Strategy 4: Model returned bare array - wrap in common keys
        text_stripped = text.strip()
        if text_stripped.startswith('['):
            try:
                arr = json.loads(text_stripped)
                if isinstance(arr, list):
                    # Guess the key based on common patterns
                    for key in ['tasks', 'dates', 'people', 'decisions', 'items']:
                        return {key: arr}
            except json.JSONDecodeError:
                pass

        # Strategy 5: Extract key-value if model wrote "key": "value" without braces
        kv_match = re.match(r'\s*["\']?(\w+)["\']?\s*:\s*["\'](.+)["\']?\s*$', text_stripped, re.DOTALL)
        if kv_match:
            key, value = kv_match.groups()
            try:
                return {key: value.strip().strip('"').strip("'")}
            except:
                pass

        # Strategy 6: Model output raw text - wrap in expected JSON envelope
        # This is the LAST resort for anything that doesn't look like JSON
        if not text_stripped.startswith('{') and not text_stripped.startswith('['):
            # Looks like raw text, wrap it properly
            for key in ['draft', 'summary', 'response', 'reply', 'text']:
                try:
                    return {key: text_stripped}
                except:
                    pass

        return None

    async def agenerate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Async generate raw text (no JSON parsing).

        For chat/conversational use where the response is natural language,
        not structured JSON. Skips JSON_INSTRUCTION and _parse_json.

        Providers with native async support (e.g. Gemini) override
        _raw_agenerate for true async I/O. Others fall back to
        asyncio.to_thread.
        """
        self.ensure_initialized()
        return await self._raw_agenerate(prompt, system_prompt)

    async def _raw_agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Async raw text generation. Default: run sync version in thread pool.
        Override in providers with native async support.
        """
        import asyncio
        return await asyncio.to_thread(self._raw_generate, prompt, system_prompt)

    def ensure_initialized(self) -> None:
        """Ensure provider is initialized before use"""
        if not self._initialized:
            logger.info(f"Initializing {self.__class__.__name__}...")
            self.initialize()
            self._initialized = True

    @abstractmethod
    def cleanup(self) -> None:
        """Release resources (unload model, close connections, etc.)"""
        pass

    def get_token_usage(self) -> Dict[str, Any]:
        """Get accumulated token usage. Override in providers that track tokens."""
        return {'input_tokens': 0, 'output_tokens': 0, 'model': 'unknown'}

    def reset_token_usage(self) -> None:
        """Reset token usage counters. Override in providers that track tokens."""
        pass
