Analyze this email to understand the scheduling context.

Classify into ONE of these intent types:
- "availability_request": Sender is asking when YOU are available to meet
- "time_request": Sender is asking YOU to provide or communicate a meeting time
- "meeting_confirmation": Sender is confirming a specific meeting time
- "meeting_reminder": Sender is reminding about an already-scheduled meeting
- "reschedule_request": Sender wants to change an existing meeting time
- "none": No actionable scheduling intent

Also extract any specific times/dates mentioned.

**Subject:** {message_subject}

**Body:**
{message_body}

Respond with JSON only:
```json
{{
    "has_intent": true/false,
    "intent_type": "availability_request|time_request|meeting_confirmation|meeting_reminder|reschedule_request|none",
    "confidence": 0.0-1.0,
    "reason": "Brief explanation of what the sender wants",
    "action_required": "What the recipient needs to do",
    "meeting_with": "Name of person to meet with, if mentioned",
    "mentioned_times": ["any specific times/dates mentioned"],
    "detected_phrases": ["key phrases that indicate intent"]
}}
```
