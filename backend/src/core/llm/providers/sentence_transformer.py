"""
Sentence Transformer provider for embedding-based classification.

Uses all-MiniLM-L6-v2 for zero-shot classification via semantic similarity.
Designed for lightweight, fast CPU inference.
"""
import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of embedding-based classification"""
    label: str
    confidence: float
    scores: dict  # All label scores for transparency


class SentenceTransformerProvider:
    """
    Sentence embedding provider for classification tasks.

    Unlike BaseLLMProvider (text generation), this provider:
    - Computes embeddings, not generates text
    - Classifies via semantic similarity to anchor descriptions
    - Optimized for CPU inference

    Default model: all-MiniLM-L6-v2
    - 80MB, 6 layers, ~22M parameters
    - ~20-50ms inference on CPU
    """

    def __init__(self, model_id: str = "all-MiniLM-L6-v2"):
        self.model_id = model_id
        self.model = None
        self._initialized = False
        self._anchor_cache: dict = {}  # Cache encoded anchors

    def initialize(self) -> None:
        """Load the sentence transformer model"""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers required. Install with: "
                "pip install sentence-transformers"
            ) from e

        logger.info(f"Loading sentence transformer: {self.model_id}")
        self.model = SentenceTransformer(self.model_id)
        self._initialized = True
        logger.info(f"Model loaded successfully")

    def ensure_initialized(self) -> None:
        """Ensure model is loaded before use"""
        if not self._initialized:
            self.initialize()

    def encode(self, texts: List[str], convert_to_tensor: bool = True) -> Any:
        """
        Encode texts to embeddings.

        Args:
            texts: List of texts to encode
            convert_to_tensor: Return as tensor (for similarity computation)

        Returns:
            Embeddings tensor or numpy array
        """
        self.ensure_initialized()
        return self.model.encode(texts, convert_to_tensor=convert_to_tensor)

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
        from sentence_transformers import util

        # Encode input text
        text_embedding = self.model.encode(text, convert_to_tensor=True)

        # Compute similarity to each label's anchors
        scores = {}
        for label, anchors in label_anchors.items():
            # Use cached anchor embeddings if available
            cache_key = (label, tuple(anchors))
            if cache_key not in self._anchor_cache:
                self._anchor_cache[cache_key] = self.model.encode(
                    anchors, convert_to_tensor=True
                )
            anchor_embeddings = self._anchor_cache[cache_key]

            # Max similarity to any anchor for this label
            similarities = util.cos_sim(text_embedding, anchor_embeddings)
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
        from sentence_transformers import util

        if not texts:
            return []

        # Batch encode all texts
        text_embeddings = self.model.encode(texts, convert_to_tensor=True)

        # Encode and cache anchors
        anchor_embeddings_map = {}
        for label, anchors in label_anchors.items():
            cache_key = (label, tuple(anchors))
            if cache_key not in self._anchor_cache:
                self._anchor_cache[cache_key] = self.model.encode(
                    anchors, convert_to_tensor=True
                )
            anchor_embeddings_map[label] = self._anchor_cache[cache_key]

        # Classify each text
        results = []
        for i, text_emb in enumerate(text_embeddings):
            scores = {}
            for label, anchor_emb in anchor_embeddings_map.items():
                similarities = util.cos_sim(text_emb.unsqueeze(0), anchor_emb)
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
        if self.model is not None:
            del self.model
            self.model = None
        self._anchor_cache.clear()
        self._initialized = False
        logger.info("Sentence transformer unloaded")

    def is_available(self) -> bool:
        """Check if sentence-transformers is installed"""
        try:
            import sentence_transformers
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
