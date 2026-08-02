"""
HuggingFace Transformers provider for local model inference.
Default: Qwen/Qwen2.5-0.5B-Instruct
"""
import logging
from typing import Any, Dict, List, Optional

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class HFTransformersProvider(BaseLLMProvider):
    """
    Local inference using HuggingFace Transformers.

    Optimized for Qwen2.5-0.5B-Instruct:
    - 128K context window
    - 8K output tokens
    - Runs on CPU or GPU
    """

    def __init__(self, config: Any):
        super().__init__(config)
        self.model = None
        self.tokenizer = None
        self.device = None
        self._torch = None

    def initialize(self) -> None:
        """Load model and tokenizer"""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "transformers and torch required. Install with: "
                "pip install transformers torch"
            ) from e

        self._torch = torch
        model_id = self.config.hf_model_id
        logger.info(f"Loading model: {model_id}")

        if self.config.hf_device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = self.config.hf_device

        logger.info(f"Using device: {self.device}")

        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }

        if self.config.hf_torch_dtype == "auto":
            torch_dtype = torch.float16 if self.device != "cpu" else torch.float32
        else:
            torch_dtype = dtype_map.get(self.config.hf_torch_dtype, torch.float32)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            cache_dir=self.config.cache_dir,
            trust_remote_code=True,
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            device_map=self.device if self.device != "cpu" else None,
            cache_dir=self.config.cache_dir,
            trust_remote_code=True,
        )

        if self.device == "cpu":
            self.model = self.model.to(self.device)

        self.model.eval()
        self._initialized = True
        logger.info(f"Model loaded successfully on {self.device}")

    def _raw_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        *,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Internal: Generate raw text using chat template"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Apply chat template
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        # Tokenize
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        # Check input length
        input_length = inputs.input_ids.shape[1]
        if input_length > self.config.hf_max_input_tokens:
            logger.warning(
                f"Input length {input_length} exceeds max {self.config.hf_max_input_tokens}, truncating"
            )
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                max_length=self.config.hf_max_input_tokens,
                truncation=True,
            ).to(self.model.device)

        with self._torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_output_tokens or self.config.hf_max_new_tokens,
                temperature=self.config.hf_temperature if temperature is None else temperature,
                top_p=self.config.hf_top_p,
                do_sample=(self.config.hf_temperature if temperature is None else temperature) > 0,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        response = self.tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True,
        )

        return response.strip()

    def _raw_generate_batch(self, prompts: List[str], system_prompt: Optional[str] = None) -> List[str]:
        """
        Internal: Batch generate raw text using left-padding.
        Efficient GPU batching for multiple prompts.
        """
        all_texts = []
        for prompt in prompts:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            all_texts.append(text)

        # Set left padding for batched generation (required for causal LMs)
        original_padding_side = self.tokenizer.padding_side
        self.tokenizer.padding_side = "left"

        # Ensure pad token is set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        try:
            inputs = self.tokenizer(
                all_texts,
                padding=True,
                truncation=True,
                max_length=self.config.hf_max_input_tokens,
                return_tensors="pt",
            ).to(self.model.device)

            with self._torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config.hf_max_new_tokens,
                    temperature=self.config.hf_temperature,
                    top_p=self.config.hf_top_p,
                    do_sample=self.config.hf_temperature > 0,
                    pad_token_id=self.tokenizer.eos_token_id,
                )

            results = []
            input_len = inputs.input_ids.shape[1]
            for output in outputs:
                response = self.tokenizer.decode(
                    output[input_len:],
                    skip_special_tokens=True,
                )
                results.append(response.strip())

            return results

        finally:
            self.tokenizer.padding_side = original_padding_side

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Batch generate JSON with efficient GPU batching.
        Failed parses are retried individually.
        """
        from .base import JSON_INSTRUCTION, REPAIR_PROMPT

        if not prompts:
            return []

        if len(prompts) == 1:
            return [self.generate(prompts[0], system_prompt)]

        self.ensure_initialized()

        full_system = (system_prompt or "") + JSON_INSTRUCTION
        raw_results = self._raw_generate_batch(prompts, full_system)

        # Parse results, track failures for retry
        results = []
        failed_indices = []

        for i, raw in enumerate(raw_results):
            parsed = self._parse_json(raw)
            if "_error" in parsed:
                failed_indices.append((i, prompts[i], raw))
            results.append(parsed)

        # Retry failed parses individually
        for idx, original_prompt, raw in failed_indices:
            retry_prompt = REPAIR_PROMPT.format(raw=raw[:500])
            retry_raw = self._raw_generate(retry_prompt, full_system)
            results[idx] = self._parse_json(retry_raw)

        return results

    def cleanup(self) -> None:
        """Unload model to free memory"""
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None

        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()
            self._torch = None

        self._initialized = False
        logger.info("Model unloaded")
