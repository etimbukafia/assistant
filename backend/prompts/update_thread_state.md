You are updating the state of an email thread based on a new message.

**TODAY'S DATE:** {current_date}
**CURRENT THREAD STATE:**
- **Summary:** {thread_summary}
- **Participants:** {participants}
- **Open Tasks:** {open_tasks}
- **Decisions Made:** {decisions}
- **Action Points:** {action_points}
- **Last Action:** {last_action}
- **Message Count:** {message_count}

---

**NEW MESSAGE:**
- **From:** {sender}
- **Subject:** {subject}
- **Body:** {body}

---

**YOUR TASK:**
Analyze the new message and produce a STATE DELTA - what has changed.

**Rules:**
1. **Summary**: Update only if the conversation topic has evolved or narrowed
2. **Tasks**:
   - Mark existing tasks as "completed" if this message indicates completion
   - Mark existing tasks as "superseded" if this message makes them obsolete
   - Add new tasks ONLY if they are genuinely new (not duplicates of existing)
   - **DEDUPLICATION CHECK**: Before adding a new task, check if open_tasks already has a semantically similar task. If so, DON'T add another:
     - "Respond to meeting request" ≈ "Respond to John regarding meeting request" → SKIP
     - "Review Q4 budget" ≈ "Review Q4 budget proposal" → SKIP
     - Use SHORT, NORMALIZED titles (put recipient/details in description, not title)
   - Each task needs: title, description, type (explicit/implied_followup/waiting_for)
3. **Deadline Extraction**: Extract deadlines ONLY when an explicit date/time is mentioned
   - **Extract**: "by Friday", "before 5pm Jan 10", "due March 3rd", "deadline is tomorrow"
   - **DO NOT extract**: "ASAP", "urgently", "as soon as possible", "when you get a chance"
   - Set priority="urgent" for urgency keywords, but DO NOT create a deadline from them
   - Omit deadline field entirely if no explicit date is mentioned
4. **Decisions**: Add only new decisions made in THIS message
5. **Last Action**: What meaningful action does this message represent?
6. **Needs Reply**: Does the thread now require a response from the user?
7. **Action Points**: Update the executive-scan action points list.
   - Remove completed/resolved items, add new ones from THIS message
   - Short imperative or declarative sentences (max 5 total)
   - Only genuinely actionable or situationally important items
   - No fluff, no restating the subject line
8. **Scheduling Intent**: Does THIS message contain scheduling intent?
   - "availability_request": They're asking when you're free
   - "time_request": They're asking you to provide/confirm a specific time
   - "meeting_confirmation": They're confirming a time that was discussed
   - "meeting_reminder": Reminding about an existing meeting
   - "reschedule_request": They want to change an existing meeting
   - "none": No actionable scheduling intent

**Return JSON:**
```json
{{
    "summary_update": "Updated summary if changed, or null if unchanged",
    "task_updates": [
        {{
            "existing_task_title": "Title of existing task",
            "new_status": "completed|superseded",
            "reason": "Why this task is now completed/superseded"
        }}
    ],
    "new_tasks": [
        {{
            "title": "Task title",
            "description": "What needs to be done",
            "task_type": "explicit|implied_followup|waiting_for",
            "priority": "low|normal|high|urgent",
            "source_snippet": "Quote from message that created this task",
            "deadline": {{
                "date": "2025-01-20T17:00:00",
                "source": "explicit|inferred",
                "confidence": 0.95,
                "original_text": "by Friday 5pm"
            }}
        }}
    ],
    "new_decisions": [
        {{
            "decision": "What was decided",
            "made_by": "Who made this decision"
        }}
    ],
    "last_action": "Brief description of the action in this message",
    "last_action_by": "Email of who took the action",
    "needs_reply": true/false,
    "needs_reply_reason": "Why does/doesn't this need a reply",
    "action_points": ["Updated action point 1", "New action point from this message"],
    "scheduling_intent": true/false,
    "scheduling_intent_type": "availability_request|time_request|meeting_confirmation|meeting_reminder|reschedule_request|none",
    "scheduling_intent_confidence": 0.0-1.0
}}
```
