Evaluate if a task reminder should be sent now based on current context.

**Task Details:**
- **Title:** {task_title}
- **Created:** {task_created_at}
- **Reminder Context:** {reminder_context}
- **Last Reminded:** {last_reminded_at}
- **Reminder Count:** {reminder_count}

**Source Message:**
- **Subject:** {message_subject}
- **From:** {message_sender}

**Current Time:** {current_time}

**Evaluation Criteria:**

1. **Timing**: Has the scheduled reminder time arrived?
2. **Relevance**: Is the task still relevant? (deadline not passed, task still active)
3. **Frequency**: Are we reminding too often? (should limit to once per day max)
4. **Context**: For waiting_for_response type - has there been any update?

**Decision Logic:**

**SEND REMINDER if:**
- Scheduled time has arrived
- Task is still pending/active
- Haven't reminded in last 24 hours (or this is first reminder)
- Deadline approaching (within offset window)
- For meeting_prep: meeting is upcoming and prep time needed
- For waiting_for_response: reasonable time has passed with no update

**DON'T SEND REMINDER if:**
- Too early (scheduled time not reached)
- Already reminded recently (< 24 hours ago)
- Deadline has passed (task is overdue and stale)
- For meeting_prep: meeting already happened
- For waiting_for_response: response was received (check if needed)

**RESCHEDULE if:**
- It's too early - reschedule for the proper time
- Reminded too recently - reschedule for 24 hours from last reminder
- In middle of night - reschedule for morning (8am)

**Output Format:**

Return ONLY valid JSON with this exact structure:

```json
{{
  "should_remind": true,
  "reason": "Concise explanation of decision (1-2 sentences)",
  "reschedule_for": null,
  "suggested_message": "Reminder: [Task title]. [Context from original email]"
}}
```

OR if not reminding:

```json
{{
  "should_remind": false,
  "reason": "Concise explanation why not reminding",
  "reschedule_for": "2025-01-18T08:00:00",
  "suggested_message": null
}}
```

**Guidelines:**

- `should_remind`: Boolean - whether to send reminder now
- `reason`: Clear explanation for the decision
- `reschedule_for`: ISO datetime string if should check again later, null if no reschedule needed
- `suggested_message`: Helpful reminder text that provides context, null if not reminding

**Examples:**

Example 1 - Send Reminder:
```json
{{
  "should_remind": true,
  "reason": "Deadline is tomorrow and no recent reminders sent",
  "reschedule_for": null,
  "suggested_message": "Reminder: Send Q4 budget breakdown to John (due tomorrow, Wednesday)"
}}
```

Example 2 - Reschedule (too early):
```json
{{
  "should_remind": false,
  "reason": "Scheduled reminder time is still 6 hours away",
  "reschedule_for": "2025-01-17T14:00:00",
  "suggested_message": null
}}
```

Example 3 - Reschedule (too frequent):
```json
{{
  "should_remind": false,
  "reason": "Already reminded 8 hours ago, waiting for 24 hour interval",
  "reschedule_for": "2025-01-18T09:00:00",
  "suggested_message": null
}}
```

Example 4 - Don't remind (passed deadline):
```json
{{
  "should_remind": false,
  "reason": "Deadline was yesterday, task is now overdue and stale",
  "reschedule_for": null,
  "suggested_message": null
}}
```

Return ONLY the JSON object. No other text.
