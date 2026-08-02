"""
Memory boundary for product automations.

Automations must consume stored context through hardened memory services and filters
rather than raw, ad hoc context queries. The current approved boundary is:

- `app.services.context_memory_policy` for confidence, lifecycle, and historical-expiry rules
- `app.services.contact_brief` / `app.services.contact_timeline` for relationship context
- `app.superpowers.email_drafting.EmailDraftingService` for draft generation
- `app.superpowers.meeting_brief.MeetingBriefService` for event-scoped brief generation

This keeps forgotten entries excluded, low-confidence memory out of retrieval, and
deleted-source/provenance behavior consistent across the product.
"""

from __future__ import annotations

MEMORY_BOUNDARY_COMPONENTS = (
    "context_memory_policy",
    "contact_brief",
    "contact_timeline",
    "email_drafting",
    "meeting_brief",
)
