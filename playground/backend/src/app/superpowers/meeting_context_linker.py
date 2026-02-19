"""Attach context entries to calendar events (placeholder)."""

from typing import Any, Dict, List


class MeetingContextLinker:
    """Links context entries with calendar events."""

    def __init__(self, *args, **kwargs) -> None:
        self._config = kwargs

    def attach_context(
        self,
        event_id: str,
        context_entry_ids: List[int],
    ) -> Dict[str, Any]:
        _ = (event_id, context_entry_ids)
        return {"event_id": event_id, "context_entry_ids": context_entry_ids}

    def list_context(self, event_id: str) -> List[Dict[str, Any]]:
        _ = event_id
        return []

    def remove_context(self, event_id: str, context_entry_id: int) -> Dict[str, Any]:
        _ = (event_id, context_entry_id)
        return {"event_id": event_id, "removed": context_entry_id}
