# Prompts Directory

This directory contains all AI prompts used by the application, following SOLID principles for better maintainability and version control.

## Prompt Files

- `process_message.md` - Main prompt for processing emails with all extraction features
- `summarize.md` - Prompt for generating email summaries
- `classify_needs_reply.md` - Prompt for classifying if an email needs a reply
- `extract_tasks.md` - Prompt for extracting tasks and action items
- `extract_dates.md` - Prompt for extracting dates and deadlines
- `extract_people.md` - Prompt for extracting people names
- `extract_decisions.md` - Prompt for extracting decisions
- `draft_reply.md` - Prompt for generating draft replies

## Template Variables

Each prompt uses Python string formatting with named placeholders:

- `{sender}` - Email sender
- `{subject}` - Email subject
- `{body}` - Email body content
- `{text}` - Generic text content
- `{context_section}` - Additional context (optional)

## Usage

Prompts are loaded automatically by `AIProcessor` class using the `_load_prompt()` method with caching for performance.

## Best Practices

1. Keep prompts clear and focused on single responsibility
2. Use markdown formatting for better readability
3. Include explicit instructions about expected output format
4. Document any template variables in the prompt itself
5. Version control all prompt changes for tracking improvements
