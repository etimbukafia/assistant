"""
LLM Configuration
"""
from dataclasses import dataclass
from typing import Optional, Literal



@dataclass
class LLMConfig:
    """Configuration for LLM Orchestrator"""

    # Provider selection (default: gemini for both Gemini and Gemma models)
    provider: Literal["huggingface", "gemini"] = "gemini"

    # HuggingFace settings (Qwen2.5-0.5B: 128K context, 8K output)
    hf_model_id: str = "Qwen/Qwen2.5-0.5B-Instruct"
    hf_device: str = "auto"  # "auto", "cpu", "cuda", "mps"
    hf_torch_dtype: str = "auto"  # "auto", "float16", "bfloat16", "float32"
    hf_max_new_tokens: int = 4096  # Qwen supports up to 8K output
    hf_max_input_tokens: int = 65536  # 64K input, safe within 128K context
    hf_temperature: float = 0.1  # Low for consistent structured output
    hf_top_p: float = 0.9

    # Gemini settings - default model used when no task-specific override
    gemini_model: str = "gemma-3-4b-it"  # Free Gemma model as safe default
    gemini_api_key: Optional[str] = None
    gemini_max_input_tokens: int = 131072  # 128K practical limit
    gemini_max_output_tokens: int = 8192

    # Inference settings
    timeout_seconds: int = 120

    # Caching
    cache_dir: Optional[str] = None  # HuggingFace cache directory

    # Batch processing
    batch_size: int = 1  # Process N items per inference call

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables"""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        return cls(
            provider=os.getenv("LLM_PROVIDER", "gemini"),
            hf_model_id=os.getenv("LLM_HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"),
            hf_device=os.getenv("LLM_HF_DEVICE", "auto"),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            cache_dir=os.getenv("HF_HOME"),
        )

    @classmethod
    def for_email(cls) -> "LLMConfig":
        """Config for email processing (summarization, extraction, classification).

        Default: gemma-3-4b-it (free Gemma model, no credits consumed)
        """
        import os
        config = cls.from_env()

        # Apply email-specific overrides (env vars take precedence)
        provider = os.getenv("LLM_EMAIL_PROVIDER", "gemini")
        model = os.getenv("LLM_EMAIL_MODEL", "gemma-3-4b-it")

        config.provider = provider
        if config.provider == "gemini":
            config.gemini_model = model
        else:
            config.hf_model_id = model
        return config

    @classmethod
    def for_chat(cls) -> "LLMConfig":
        """Config for chat conversations and reply drafting.

        Default: gemini-2.5-flash-lite (paid Gemini model, consumes credits)
        """
        import os
        config = cls.from_env()

        # Apply chat-specific overrides (env vars take precedence)
        provider = os.getenv("LLM_CHAT_PROVIDER", "gemini")
        model = os.getenv("LLM_CHAT_MODEL", "gemini-2.5-flash-lite")

        config.provider = provider
        if config.provider == "gemini":
            config.gemini_model = model
        else:
            config.hf_model_id = model
        return config
