Extract scheduling details from this email.

**Subject:** {message_subject}
**From:** {sender_email}

**Body:**
{message_body}

Extract:
1. Participants (email addresses or names mentioned)
2. Time constraints (specific times, date ranges, or relative dates like "next week")
3. Meeting type (call, review, demo, coffee, interview, or other)
4. Duration if mentioned (in minutes)
5. Timezone if mentioned (in IANA format like "America/New_York")

Respond with JSON only:
```json
{{
    "participants": ["email or name"],
    "time_constraints": {{
        "specific_times": ["any specific times mentioned"],
        "date_range": {{
            "start": "YYYY-MM-DD or null",
            "end": "YYYY-MM-DD or null"
        }},
        "relative_reference": "e.g., 'next week', 'tomorrow', or null"
    }},
    "meeting_type": "call|review|demo|coffee|interview|other",
    "duration_minutes": 30,
    "timezone": "detected timezone or null",
    "source_snippet": "the exact text that indicates scheduling intent"
}}
```
