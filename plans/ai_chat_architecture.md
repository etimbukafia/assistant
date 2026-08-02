# AI Chat Architecture

## Decision Router

Layer 1: Conversational Layer (No tools)
For small talk or trivial/simple/stateless questions/messages

Layer 2: Actionable Workflows
Decision framework : "Does the user want me to perform an action, contains any of these intents or contains a mention (@)

If the decision router cannot confidently say it's layer 2, it should either:
- default to layer 1 or ask a gentle clarification question

Example Handling:
User: "Help me prep for a tense conversation with an investor"

Not a strict tool intent
Teeks should route to layer 1



## Two step architecture (Layer 2)

### Planning step: 
When user message arrives:

#### Parse intents
Intent Taxonomy:
For each intent taxonomy, we have to define all that they need (context), so we know when to ask clarifying questions. Key emphasis on "need", example, the ai shouldn't "need" the recipient name before it can draft an email.

Intents:
- draft_email_reply
- draft_reply
- summarize
- extract_tasks
- create_event (schedule_meeting)
- reschedule_meeting
- cancel_meeting
- check_availability
- send_email
- extract_task
- create_task
- extract_commitment
- create_commitment
- extract_decision
- create_decision
- extract_risk
- create_risk
- extract_contact
- create_contact
- draft_meeting_brief/meeting_prep
- recap (day/week/month etc)
- status_check
- relationship_insight
- knowledge_lookup
- day/week planning

#### Split into atomic tasks: 

"Reply to John, Reply to James, schedule a call with James for next week, and draft a meeting brief for the call".
That's four actions:
1. Draft reply to John
2. Draft reply to James
3. Schedule meeting
4. meeting brief

Group actions by tool calls: 
- draft_email_reply tool actions together
- create_event 
- meeting_prep tool
	
#### Order the tasks

#### Ask a single clarifying question if anything is blocking
#### Pass for execution in a json

Example: {
  "intents": [
    {"type": "draft_email", "depends_on": ["get_context"], "tool": "draft_email"},
    {"type": "check_availability", "tool": "check_availability"},
    {"type": "create_meeting", "tool": "create_meeting"}
  ],
  "missing_info": ["which calendar", "duration"],
  "clarify_if_blocking": true
  "one_clarifying_question_asked": false
}

#### Handle dependencies explicitly
Some actions require others.
Examples:
- "Schedule a meeting" depends on "get_availabilty"
- "Send reply" depends on "draft reply" or a user's message and user approval

Planner should label dependencies and enforce ordering





### Execution step

#### Use "Partial completion by default"
Do not block the whole request because one part is unclear
Example:
User: "Schedule with Sarah next week and also draft a reply"

If scheduling needs duration or time:
- Draft the reply immediately
- Ask clarifying question for scheduling
- Offer suggested times

#### Ask one question, not five
When clarification is needed, ask the minimum needed to proceed. Make intelligent assumptions based on the context and info in disposal and present them when asking the clarifying question.

#### Use a confirm-before-act gate for write operations (operations that changes something)

#### Keep a visible plan in the ui
Huge for trust. Show a small checklist so the human assistant (user) can approve or tweak

#### Use session context for understanding intent
Users often add follow-ups like:
"Actually make it 45 minutes, and invite Jane too"
Alone they seem confusing, but with the session context it makes more sense and clearer.
Create an intent memory or task state:
- active task
- pending tasks
- pending questions
- actions done

Implementation pattern that works well
- planner() -> Return Json plan
- resolver() -> fills missing defaults / asks 1 clarifying question if needed
- executor() -> runs tools/ performs action
- presenter() -> formats output + checklist
- commit () -> executes final action on approval for write operations 

# Recommended by Codex
Plan to add lightweight planning without new services

  1. Define supported intent taxonomy (only what we have tools for).
      - draft_email_reply, meeting_brief/prep, schedule/reschedule, recap/summary, extract_decisions/commitments/risks, task_create/update, preferences update, knowledge lookup.
  2. Add planner hint inside orchestrator turn.
      - Before LLM call, add a system note: “If multiple intents/targets, produce a short ordered plan and execute up to 5 actions now. Ask one concise question only if truly blocking. Otherwise proceed.”
      - Keep hidden; no UI change.
  3. Enforce single clarifying question.
      - Post-process assistant text: if more than one question mark OR multiple bullet questions, compress to one combined question.
  4. Keep batching and action cap.
      - Reuse our multi-entity batch instruction and MAX_ACTION_TOOLS_PER_TURN=5.
      - Defer extras with the existing defer/continue flow.
  5. Guard unsupported intents.
      - If LLM surfaces an intent outside taxonomy, return a concise “not supported yet” instead of meandering.
  6. Optional small UI hint later (not now): show a tiny “Working on: X, Y (5 max)” chip in chat to build trust.