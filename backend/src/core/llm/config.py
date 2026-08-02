"""
LLM Configuration
"""
from dataclasses import dataclass
from typing import Literal, Optional


ProviderLiteral = Literal["huggingface", "gemini", "anthropic"]


def _apply_workload_overrides(
    config: "LLMConfig",
    *,
    provider_env: str,
    model_env: str,
    default_provider: ProviderLiteral,
    default_model: str,
) -> "LLMConfig":
    import os

    provider = os.getenv(provider_env, default_provider).strip().lower() or default_provider
    model = os.getenv(model_env, default_model).strip() or default_model

    config.provider = provider  # type: ignore[assignment]
    if config.provider == "gemini":
        config.gemini_model = model
    elif config.provider == "anthropic":
        config.anthropic_model = model
    else:
        config.hf_model_id = model
    return config


@dataclass
class LLMConfig:
    """Configuration for LLM Orchestrator."""

    # Provider selection (default: gemini for both Gemini and Gemma models)
    provider: ProviderLiteral = "gemini"

    # HuggingFace settings (Qwen2.5-0.5B: 128K context, 8K output)
    hf_model_id: str = "Qwen/Qwen2.5-0.5B-Instruct"
    hf_device: str = "auto"  # "auto", "cpu", "cuda", "mps"
    hf_torch_dtype: str = "auto"  # "auto", "float16", "bfloat16", "float32"
    hf_max_new_tokens: int = 4096  # Qwen supports up to 8K output
    hf_max_input_tokens: int = 65536  # 64K input, safe within 128K context
    hf_temperature: float = 0.1  # Low for consistent structured output
    hf_top_p: float = 0.9

    # Hosted provider settings
    gemini_model: str = "gemma-3-4b-it"  # Free Gemma model as safe default
    gemini_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_api_key: Optional[str] = None
    api_max_input_tokens: int = 131072
    api_max_output_tokens: int = 8192

    # Inference settings
    timeout_seconds: int = 120

    # Caching
    cache_dir: Optional[str] = None  # HuggingFace cache directory

    # Batch processing
    batch_size: int = 1  # Process N items per inference call

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables."""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        return cls(
            provider=os.getenv("LLM_PROVIDER", "gemini").strip().lower(),
            hf_model_id=os.getenv("LLM_HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"),
            hf_device=os.getenv("LLM_HF_DEVICE", "auto"),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            cache_dir=os.getenv("HF_HOME"),
        )

    @classmethod
    def for_email(cls) -> "LLMConfig":
        """Config for email processing (summarization, extraction, classification)."""
        config = cls.from_env()
        return _apply_workload_overrides(
            config,
            provider_env="LLM_EMAIL_PROVIDER",
            model_env="LLM_EMAIL_MODEL",
            default_provider="gemini",
            default_model="gemma-3-4b-it",
        )

    @classmethod
    def for_chat(cls) -> "LLMConfig":
        """Config for chat conversations."""
        config = cls.from_env()
        return _apply_workload_overrides(
            config,
            provider_env="LLM_CHAT_PROVIDER",
            model_env="LLM_CHAT_MODEL",
            default_provider="gemini",
            default_model="gemini-2.5-flash-lite",
        )

    @classmethod
    def for_drafting(cls) -> "LLMConfig":
        """Config for user-facing drafting workloads."""
        import os

        config = cls.from_env()
        default_provider = os.getenv("LLM_CHAT_PROVIDER", "gemini")
        default_model = os.getenv("LLM_CHAT_MODEL", "gemini-2.5-flash-lite")
        return _apply_workload_overrides(
            config,
            provider_env="LLM_DRAFT_PROVIDER",
            model_env="LLM_DRAFT_MODEL",
            default_provider=default_provider,
            default_model=default_model,
        )
