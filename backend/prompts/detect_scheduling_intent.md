**Scheduling Intent** - Does this email contain a scheduling action?

Intent types:
- `availability_request`: Sender asking when YOU are free / available
- `time_request`: Sender asking YOU to propose or confirm a meeting time
- `meeting_confirmation`: Sender confirming a specific time that was discussed
- `meeting_reminder`: Sender reminding about an already-scheduled meeting
- `reschedule_request`: Sender wants to change an existing meeting time
- `none`: No scheduling action needed

If detected, also provide:
- `summary`: One natural sentence describing what the sender wants, written from your perspective. E.g. "Sarah asked when you are free for the Q4 review meeting" or "John confirmed the Wednesday 2pm call". Keep it under 20 words.
- `meeting_title`: The clean name of the meeting or event being discussed. E.g. "Q4 Review", "End-of-year dinner", "Onboarding call". Null if not specified.
- `meeting_date`: The specific date mentioned as ISO format (YYYY-MM-DD). Null if no specific date is mentioned.
