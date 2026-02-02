"""
Sentence Transformer provider for embedding-based classification.

Uses all-MiniLM-L6-v2 (ONNX) for zero-shot classification via semantic similarity.
Designed for lightweight, fast CPU inference without PyTorch dependency.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

REPO_ID = "sentence-transformers/all-MiniLM-L6-v2"
ONNX_FILENAME = "onnx/model.onnx"


@dataclass
class ClassificationResult:
    """Result of embedding-based classification"""
    label: str
    confidence: float
    scores: dict  # All label scores for transparency


def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Mean pooling with attention mask, matching sentence-transformers behavior."""
    mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
    summed = np.sum(token_embeddings * mask_expanded, axis=1)
    count = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
    return summed / count


def _normalize(embeddings: np.ndarray) -> np.ndarray:
    """L2-normalize embeddings."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.clip(norms, a_min=1e-9, a_max=None)
    return embeddings / norms


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between normalized vectors. Returns (len(a), len(b)) matrix."""
    return a @ b.T


class SentenceTransformerProvider:
    """
    Sentence embedding provider for classification tasks.

    Unlike BaseLLMProvider (text generation), this provider:
    - Computes embeddings, not generates text
    - Classifies via semantic similarity to anchor descriptions
    - Optimized for CPU inference

    Default model: all-MiniLM-L6-v2 (ONNX)
    - ~80MB model, 6 layers, ~22M parameters
    - ~20-50ms inference on CPU
    """

    def __init__(self, model_id: str = "all-MiniLM-L6-v2"):
        self.model_id = model_id
        self._session = None
        self._tokenizer = None
        self._initialized = False
        self._anchor_cache: dict = {}  # Cache encoded anchors

    def initialize(self) -> None:
        """Load the ONNX model and tokenizer"""
        if self._initialized:
            return

        try:
            import onnxruntime as ort
            from huggingface_hub import hf_hub_download
            from tokenizers import Tokenizer
        except ImportError as e:
            raise ImportError(
                "onnxruntime, tokenizers, and huggingface-hub required. Install with: "
                "pip install onnxruntime tokenizers huggingface-hub"
            ) from e

        logger.info(f"Loading ONNX sentence transformer: {self.model_id}")

        # Download model and tokenizer from HuggingFace Hub
        model_path = hf_hub_download(repo_id=REPO_ID, filename=ONNX_FILENAME)
        tokenizer_path = hf_hub_download(repo_id=REPO_ID, filename="tokenizer.json")

        # Initialize ONNX runtime session (CPU)
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 1
        self._session = ort.InferenceSession(
            model_path, sess_options, providers=["CPUExecutionProvider"]
        )

        # Load tokenizer
        self._tokenizer = Tokenizer.from_file(tokenizer_path)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self._tokenizer.enable_truncation(max_length=256)

        self._initialized = True
        logger.info("ONNX model loaded successfully")

    def ensure_initialized(self) -> None:
        """Ensure model is loaded before use"""
        if not self._initialized:
            self.initialize()

    def encode(self, texts: List[str], convert_to_tensor: bool = True) -> Any:
        """
        Encode texts to embeddings.

        Args:
            texts: List of texts to encode
            convert_to_tensor: Kept for API compatibility (always returns numpy)

        Returns:
            Numpy array of shape (len(texts), 384)
        """
        self.ensure_initialized()

        if isinstance(texts, str):
            texts = [texts]

        # Tokenize
        encoded = self._tokenizer.encode_batch(texts)

        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

        # Run ONNX inference
        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )

        # outputs[0] is token_embeddings: (batch, seq_len, hidden_dim)
        token_embeddings = outputs[0]

        # Mean pooling + L2 normalize (same as sentence-transformers)
        embeddings = _mean_pool(token_embeddings, attention_mask)
        embeddings = _normalize(embeddings)

        return embeddings

    def classify(
        self,
        text: str,
        label_anchors: dict,
        threshold: float = 0.1,
        default_label: str = None,
    ) -> ClassificationResult:
        """
        Zero-shot classification via semantic similarity.

        Args:
            text: Text to classify
            label_anchors: Dict of {label: [anchor_descriptions]}
                Example: {"important": ["urgent business email", ...],
                          "ignore": ["promotional newsletter", ...]}
            threshold: Minimum score difference for confident classification.
                       If below threshold, returns default_label.
            default_label: Label to return when ambiguous. If None, uses
                           the label with highest score regardless.

        Returns:
            ClassificationResult with label, confidence, and all scores
        """
        self.ensure_initialized()

        # Encode input text
        text_embedding = self.encode(text)  # (1, 384)

        # Compute similarity to each label's anchors
        scores = {}
        for label, anchors in label_anchors.items():
            # Use cached anchor embeddings if available
            cache_key = (label, tuple(anchors))
            if cache_key not in self._anchor_cache:
                self._anchor_cache[cache_key] = self.encode(anchors)
            anchor_embeddings = self._anchor_cache[cache_key]

            # Max similarity to any anchor for this label
            similarities = _cosine_similarity(text_embedding, anchor_embeddings)
            scores[label] = float(similarities.max())

        # Find best and second-best labels
        sorted_labels = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_label, best_score = sorted_labels[0]

        if len(sorted_labels) > 1:
            _, second_score = sorted_labels[1]
            score_diff = best_score - second_score
        else:
            score_diff = best_score

        # Determine confidence and final label
        confidence = score_diff

        if score_diff < threshold and default_label is not None:
            # Ambiguous - use default
            return ClassificationResult(
                label=default_label,
                confidence=confidence,
                scores=scores,
            )

        return ClassificationResult(
            label=best_label,
            confidence=confidence,
            scores=scores,
        )

    def classify_batch(
        self,
        texts: List[str],
        label_anchors: dict,
        threshold: float = 0.1,
        default_label: str = None,
    ) -> List[ClassificationResult]:
        """
        Batch classification for efficiency.

        Args:
            texts: List of texts to classify
            label_anchors: Dict of {label: [anchor_descriptions]}
            threshold: Minimum score difference for confident classification
            default_label: Label to return when ambiguous

        Returns:
            List of ClassificationResult
        """
        self.ensure_initialized()

        if not texts:
            return []

        # Batch encode all texts
        text_embeddings = self.encode(texts)  # (N, 384)

        # Encode and cache anchors
        anchor_embeddings_map = {}
        for label, anchors in label_anchors.items():
            cache_key = (label, tuple(anchors))
            if cache_key not in self._anchor_cache:
                self._anchor_cache[cache_key] = self.encode(anchors)
            anchor_embeddings_map[label] = self._anchor_cache[cache_key]

        # Classify each text
        results = []
        for i in range(len(text_embeddings)):
            text_emb = text_embeddings[i:i+1]  # Keep as (1, 384)
            scores = {}
            for label, anchor_emb in anchor_embeddings_map.items():
                similarities = _cosine_similarity(text_emb, anchor_emb)
                scores[label] = float(similarities.max())

            sorted_labels = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            best_label, best_score = sorted_labels[0]

            if len(sorted_labels) > 1:
                _, second_score = sorted_labels[1]
                score_diff = best_score - second_score
            else:
                score_diff = best_score

            if score_diff < threshold and default_label is not None:
                label = default_label
            else:
                label = best_label

            results.append(ClassificationResult(
                label=label,
                confidence=score_diff,
                scores=scores,
            ))

        return results

    def cleanup(self) -> None:
        """Unload model to free memory"""
        if self._session is not None:
            del self._session
            self._session = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        self._anchor_cache.clear()
        self._initialized = False
        logger.info("Sentence transformer unloaded")

    def is_available(self) -> bool:
        """Check if onnxruntime is installed"""
        try:
            import onnxruntime
            return True
        except ImportError:
            return False


# Singleton instance for reuse across requests
_default_provider: Optional[SentenceTransformerProvider] = None


def get_sentence_transformer(
    model_id: str = "all-MiniLM-L6-v2"
) -> SentenceTransformerProvider:
    """
    Get the singleton sentence transformer provider.

    Reuses the same model instance across calls for efficiency.
    """
    global _default_provider

    if _default_provider is None:
        _default_provider = SentenceTransformerProvider(model_id)

    return _default_provider
