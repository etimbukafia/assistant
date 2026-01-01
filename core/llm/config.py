"""
LLM Configuration
"""
from dataclasses import dataclass
from typing import Optional, Literal



@dataclass
class LLMConfig:
    """Configuration for LLM Orchestrator"""

    # Provider selection
    provider: Literal["huggingface", "gemini"] = "huggingface"

    # HuggingFace settings (Qwen2.5-0.5B: 128K context, 8K output)
    hf_model_id: str = "Qwen/Qwen2.5-0.5B-Instruct"
    hf_device: str = "auto"  # "auto", "cpu", "cuda", "mps"
    hf_torch_dtype: str = "auto"  # "auto", "float16", "bfloat16", "float32"
    hf_max_new_tokens: int = 4096  # Qwen supports up to 8K output
    hf_max_input_tokens: int = 65536  # 64K input, safe within 128K context
    hf_temperature: float = 0.1  # Low for consistent structured output
    hf_top_p: float = 0.9

    # Gemini settings (Gemini 2.5 Flash: 1M context, practical 128-200K)
    gemini_model: str = "gemini-3-flash-preview"
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
            provider=os.getenv("LLM_PROVIDER", "huggingface"),
            hf_model_id=os.getenv("LLM_HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"),
            hf_device=os.getenv("LLM_HF_DEVICE", "auto"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            cache_dir=os.getenv("HF_HOME"),
        )
