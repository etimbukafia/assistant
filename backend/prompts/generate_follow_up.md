Generate a polite, professional follow-up message for an unresolved task.

**Original Email Context:**
- **From:** {sender}
- **Subject:** {subject}
- **Snippet:** {snippet}

**Task Details:**
- **Task:** {task_title}
- **Type:** {task_type}
- **Days since created:** {days_since}
- **Previous follow-ups sent:** {reminder_count}

**Additional context:** {context}

**Guidelines:**
- Be polite and professional, not pushy
- Reference the original topic naturally
- Keep it concise (3-5 sentences)
- Don't be apologetic or overly formal
- If multiple follow-ups have been sent, acknowledge the wait appropriately
- Match the tone to the relationship implied by the email context

**Return JSON:**
```json
{
  "follow_up": "Your follow-up message here (just the body, no greeting/signature)",
  "subject_line": "Suggested subject line for the follow-up",
  "tone": "friendly|professional|urgent"
}
```
