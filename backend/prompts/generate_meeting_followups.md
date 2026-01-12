You are analyzing a completed meeting to generate follow-up action items.

**Meeting:**
- **Title:** {title}
- **Date:** {meeting_date}
- **Attendees:** {attendees}
- **Agenda:** {agenda}

**Context from related emails:**
{related_emails}

**Open tasks involving attendees:**
{open_tasks}

**Prep warnings from briefing:**
{prep_warnings}

Based on this meeting context, generate follow-up items. Consider:
1. Who needs a follow-up email and what should it cover?
2. What tasks emerged from the meeting (action items, decisions to document)?
3. What needs to be followed up on later (reminders)?
4. Were there unresolved items from the prep warnings that need action?

**Return JSON:**
```json
{
  "follow_ups": [
    {
      "type": "task|email_draft|reminder",
      "title": "Brief title",
      "description": "What needs to be done and why",
      "priority": "low|normal|high",
      "related_attendee": "email@example.com or null",
      "draft_content": "For email_draft type: the suggested email text. null for other types."
    }
  ],
  "reasoning": "Brief explanation of why these follow-ups were suggested"
}
```

Guidelines:
- Generate 3-7 actionable follow-ups
- Be specific, reference actual meeting content and attendees
- For email drafts, write professional, concise messages
- Prioritize based on urgency and importance
- Don't generate generic items - make them relevant to this specific meeting
