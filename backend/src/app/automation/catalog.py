from __future__ import annotations

from typing import Dict, List, Literal, TypedDict


AutomationId = Literal["inbox-copilot", "meeting-prep"]
AutomationStatus = Literal["needs_connection", "ready", "running", "drafts_only", "off"]


class ConnectorDefinition(TypedDict):
    id: str
    label: str
    required: bool
    description: str


class AutomationDefinition(TypedDict):
    id: AutomationId
    name: str
    outcome: str
    description: str
    safety_mode: str
    execution_mode: str
    required_connectors: List[ConnectorDefinition]
    optional_connectors: List[ConnectorDefinition]
    degraded_behavior: str | None


AUTOMATION_DEFINITIONS: Dict[AutomationId, AutomationDefinition] = {
    "inbox-copilot": {
        "id": "inbox-copilot",
        "name": "Inbox Copilot",
        "outcome": "Triage threads, extract tasks, and draft replies using stored context.",
        "description": "Inbox Copilot watches reply-needed threads, surfaces tasks, and prepares draft responses for review.",
        "safety_mode": "draft_only",
        "execution_mode": "review_required",
        "required_connectors": [
            {
                "id": "gmail",
                "label": "Gmail",
                "required": True,
                "description": "Needed to read inbox threads and prepare reply drafts.",
            },
        ],
        "optional_connectors": [],
        "degraded_behavior": None,
    },
    "meeting-prep": {
        "id": "meeting-prep",
        "name": "Meeting Prep",
        "outcome": "Generate meeting briefs, attendee context, and preparation risks before events.",
        "description": "Meeting Prep assembles briefs from calendar events, attendee memory, open work, and recent context.",
        "safety_mode": "read_only",
        "execution_mode": "automatic",
        "required_connectors": [
            {
                "id": "calendar",
                "label": "Calendar",
                "required": True,
                "description": "Needed to read upcoming events and attendee lists.",
            },
        ],
        "optional_connectors": [
            {
                "id": "gmail",
                "label": "Gmail",
                "required": False,
                "description": "Optional. Adds recent attendee email threads to each brief.",
            },
        ],
        "degraded_behavior": (
            "Meeting Prep still runs from calendar, tasks, and stored memory when Gmail is absent, "
            "but skips recent attendee thread context."
        ),
    },
}


def get_automation_definition(automation_id: str) -> AutomationDefinition:
    key = str(automation_id or "").strip().lower()
    if key not in AUTOMATION_DEFINITIONS:
        raise KeyError(key)
    return AUTOMATION_DEFINITIONS[key]  # type: ignore[index]
