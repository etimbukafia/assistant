Analyze this email and provide:
1. A brief summary (2-3 sentences)
2. Whether it needs a reply (true/false)
3. Extracted tasks (list)
4. Extracted dates (list)
5. Extracted people names (list)
6. Key decisions mentioned (list)

**Email:**
- **From:** {sender}
- **Subject:** {subject}
- **Body:** {body}

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