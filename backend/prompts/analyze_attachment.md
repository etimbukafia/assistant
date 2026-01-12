Analyze this document and extract key information.

**Document Info:**
- Filename: {filename}
- Type: {mime_type}

**Instructions:**
Analyze the attached document. Return JSON with:
- `summary`: 2-3 sentence summary of the document
- `document_type`: category (contract, report, invoice, memo, presentation, spreadsheet, image, other)
- `key_points`: array of main points or findings (max 5)
- `tasks`: array of action items or to-dos found
- `deadlines`: array of dates/deadlines mentioned (ISO format if possible)
- `decisions`: array of decisions made or commitments stated
- `people`: array of people/names mentioned

**Output JSON:**
```json
{{
  "summary": "...",
  "document_type": "...",
  "key_points": ["..."],
  "tasks": ["..."],
  "deadlines": ["..."],
  "decisions": ["..."],
  "people": ["..."]
}}
```

Return empty arrays for fields with no relevant data.
