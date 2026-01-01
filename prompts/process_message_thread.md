Analyze this email in the context of the previous conversation thread.

**Previous Messages in Thread:**
{thread_context}

---

**Current Email (to analyze):**
- **From:** {sender}
- **Subject:** {subject}
- **Body:** {body}

Based on the FULL conversation context above, provide:
1. A brief summary (2-3 sentences) that captures the current email's purpose within the ongoing conversation
2. Whether it needs a reply (true/false)
3. Extracted tasks (list) - include any tasks from this email, considering prior context
4. Extracted dates (list)
5. Extracted people names (list)
6. Key decisions mentioned (list)

Return your response as JSON with these exact keys:
```json
{{
  "summary": "...",
  "needs_reply": true/false,
  "tasks": ["task1", "task2"],
  "dates": ["date1", "date2"],
  "people": ["person1", "person2"],
  "decisions": ["decision1", "decision2"]
}}
```
