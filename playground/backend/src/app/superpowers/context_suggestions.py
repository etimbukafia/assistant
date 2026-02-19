"""AI-suggested context entries abstraction (placeholder)."""

from typing import Any, Dict, List


class ContextSuggestionService:
    """Generates suggested context entries from signals."""

    def __init__(self, *args, **kwargs) -> None:
        self._config = kwargs

    def suggest(self, signals: Dict[str, Any]) -> List[Dict[str, Any]]:
        _ = signals
        return []

    def score_suggestions(self, suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        _ = suggestions
        return suggestions
