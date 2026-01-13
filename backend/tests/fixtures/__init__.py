"""
Test fixtures and sample data for tests.

This module contains:
- Sample email data
- Sample calendar events
- Sample LLM responses
- Other test data factories
"""

# Re-export test emails for backward compatibility
from tests.llm.test_emails import EMAILS, get_email, get_all_emails

__all__ = ["EMAILS", "get_email", "get_all_emails"]
