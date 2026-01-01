Does this email require a reply?

**Email:**
- **From:** {sender}
- **Subject:** {subject}
- **Body:** {body}

**Consider:**
- Direct questions asked
- Action requests made
- Expected responses implied
- Informational (no reply) vs actionable (needs reply)

**Output JSON:**
```json
{{"needs_reply": true}}
```

**Examples:**
- Question asked → `{{"needs_reply": true}}`
- FYI/newsletter → `{{"needs_reply": false}}`
- Meeting request → `{{"needs_reply": true}}`
- Receipt/confirmation → `{{"needs_reply": false}}`