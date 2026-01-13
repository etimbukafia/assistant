# AI Chat Feature Specification

## Overview

A command + clarification interface, not a general chatbot. Mental model:

“Chat with your assistant’s brain about your work, not about anything.”

This is critical. What the AI Chat Is Allowed to Do (Phase 1)
1. Ask Questions About the Inbox / Tasks / Calendar

Examples:

“What do I need to follow up on today?”

“Summarize everything from John this week”

“Which messages are waiting on me?”

“What meetings are coming up tomorrow?”

These are read-only or explanatory queries. 2. Give Instructions (But Still Approval-Gated)

Examples:

“Draft a polite reply declining this meeting”

“Reschedule this to next week”

“Create a follow-up task for this”

“Mark similar emails as low priority”

Important:

Chat suggests or prepares

It does not execute silently

Actions still appear in the UI for approval
3. Manage Principal Memory (Explicitly)

This is where chat shines.

Examples:

“I prefer concise replies”

“Always cc legal on contracts”

“John is a VIP”

“I don’t take meetings before 10am”

Chat converts these into:

Proposed PrincipalMemory entries

Shows confirmation UI

Saves only after approval. What the AI Chat Must NOT Be (Phase 1)

❌ A second inbox
❌ A place to “chat casually”
❌ A replacement for the feed
❌ A place where actions happen invisibly

If users start living in chat, the product loses clarity. UI shows approval where needed

No special privileges.

Safety Rules (Non-Negotiable)

No direct writes

Chat cannot mutate DB directly

Everything maps to existing flows

Tasks

Scheduling

Memory updates

Every action is inspectable

Every action is reversible.

## Supportive reflection
Executive assistants:

Carry emotional labor

Absorb stress from executives

Often can’t vent “upwards”

Rarely have a neutral, confidential outlet

A private, non-judgmental AI space can be very valuable.

The Correct Mental Model (Non-Negotiable)

“A calm, confidential sounding board — not a therapist.”

Think:
- The Correct Mental Model (Non-Negotiable)

“A calm, confidential sounding board — not a therapist.”

Think:
- Perspective clarifier

- Emotional decompressor

- Professional mirror

What It SHOULD Do

✔ Validate feelings
✔ Reflect emotions
✔ Help organize thoughts
✔ Normalize stress
✔ Ask gentle clarifying questions
✔ Help reframe situations
✔ Suggest work-safe next steps

What It MUST NOT Do

❌ Diagnose
❌ Give mental health advice
❌ Suggest medication
❌ Replace human support
❌ Encourage dependency
❌ Make claims like “I understand how you feel”

No “I’m here for you no matter what” language.

Language Guidelines (Extremely Important)

Use:

- “It sounds like…”

- “That can be stressful”

- “Want to talk through options?”

Avoid:

- “You should”

- “This means you have anxiety”

- “You’re right to feel this way” (judgment)

- “I’ll help you cope” (therapy-coded)

Scope the Feature Carefully (Phase-Based)
Phase 1: Emotional Reflection Mode (Safe)
- Just like temporary chat in ChatGPT
- No memory persistence by default
- No long-term emotional profiling
- No sentiment tracking

Conversations are ephemeral (or opt-in saved)

Capabilities:
- Venting
- Reflection
- Reframing
- Drafting difficult responses
- Boundary-setting language

---

## Architecture Decisions (Phase 1)

### Infrastructure (Zero New Services)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Vector Store | Supabase pgvector | Built into existing Supabase, no new service |
| Session State | Postgres | Good enough for MVP, add Redis later if needed |
| Conversation History | Postgres | New table, existing infra |
| Response Delivery | Full response (no streaming) | Simpler for MVP, add SSE later |

### Data Retention

| Session Type | Retention | Rationale |
|--------------|-----------|-----------|
| Command/work sessions | 30 days | Useful to reference past work queries |
| Supportive reflection sessions | 24 hours | Privacy - emotional venting shouldn't persist |

- **Conversation history**: Deleted when session expires
- **No long-term emotional profiling or sentiment tracking**

### Memory Systems

| Type | Purpose | Storage |
|------|---------|---------|
| Session memory | Current conversation context | Postgres (conversation_sessions) |
| User memory | Persistent user preferences | Existing UserSettings |
| Principal memory | Facts about who they support | Existing PrincipalMemory |
| Episodic memory | Past interaction patterns | Existing DecisionPattern |

### Context Layer

Sits between data sources and LLM:
- Retrieves relevant context from DB based on user query
- Handles token budgeting (prioritize what fits in context window)
- Always injects: Principal memory, today's calendar, recent urgent items
- Query-relevant: Semantic search over emails/tasks using pgvector

### Tool Registry

Pre-defined tools the AI can invoke (not arbitrary code):

| Tool | Type | HITL Required |
|------|------|---------------|
| search_emails | Read-only | No |
| search_tasks | Read-only | No |
| get_calendar | Read-only | No |
| get_email_details | Read-only | No |
| get_thread_summary | Read-only | No |
| draft_reply | Prepare | Yes - shows draft for approval |
| create_task | Prepare | Yes - shows task for approval |
| update_principal_memory | Prepare | Yes - shows entry for approval |
| reschedule_meeting | Prepare | Yes - shows change for approval |
| add_to_calendar | Prepare | Yes - shows event for approval |
| cancel_meeting | Prepare | Yes - high-risk, shows confirmation |

**Key principle**: AI prepares, user approves. No silent mutations.

### State Management

```
┌─────────────────────────────────────────────────────┐
│ ConversationState                                   │
├─────────────────────────────────────────────────────┤
│ session_id: str                                     │
│ user_id: str                                        │
│                                                     │
│ # Entity references (what are we talking about?)   │
│ current_email_id: Optional[int]                    │
│ current_task_id: Optional[int]                     │
│ current_contact_id: Optional[int]                  │
│                                                     │
│ # Workflow (multi-step operations)                 │
│ active_workflow: Optional[str]  # "draft_reply"    │
│ workflow_data: dict             # step-specific    │
│ awaiting_input: Optional[str]   # "confirmation"   │
│                                                     │
│ # Pending interactions                             │
│ pending_options: List[dict]     # disambiguation   │
│ pending_confirmation: Optional[dict]               │
└─────────────────────────────────────────────────────┘
```

### Human-in-the-Loop (HITL) Rules

| Action Type | Autonomy | Example |
|-------------|----------|---------|
| Read-only | Full | "Summarize this email" |
| Low-risk prepare | Act + inform | Create draft (not sent) |
| Medium-risk | Confirm before | Send email, schedule meeting |
| High-risk | Always confirm + explain | Delete, cancel, reply-all |

### Personality Guidelines

**Traits:**
- Professional but warm (EAs deal with high-stakes situations)
- Concise (EAs are busy)
- Proactively helpful (anticipate needs)
- Discreet (handle sensitive info appropriately)
- Confident but humble (clear recommendations, acknowledge uncertainty)

**Tone adaptation:**
- Match user's formality level
- Detect urgency signals and respond accordingly
- Skip pleasantries when user is stressed/rushed

**Emotional intelligence:**
- Validate feelings without diagnosing
- Help reframe stressful situations
- Suggest work-appropriate next steps
- Never claim to "understand" or replace human support

### API Endpoints (Phase 1)

```
POST /chat/sessions          - Create new chat session
GET  /chat/sessions          - List user's sessions
GET  /chat/sessions/{id}     - Get session with history
DELETE /chat/sessions/{id}   - Delete session

POST /chat/sessions/{id}/messages - Send message, get response
GET  /chat/sessions/{id}/messages - Get conversation history

POST /chat/sessions/{id}/approve/{action_id} - Approve pending action
POST /chat/sessions/{id}/reject/{action_id}  - Reject pending action
```

### Database Tables (New)

```sql
-- Chat sessions (retention varies by type)
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_settings(user_id),
    session_type TEXT DEFAULT 'command',  -- 'command' (30 days) or 'reflection' (24 hours)
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW(),
    state JSONB DEFAULT '{}'  -- ConversationState
);

-- Conversation messages
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'  -- tool calls, pending actions, etc.
);

-- Pending actions awaiting approval
CREATE TABLE chat_pending_actions (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,  -- 'draft_reply', 'create_task', etc.
    action_data JSONB NOT NULL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for cleanup job
CREATE INDEX ix_chat_sessions_last_activity ON chat_sessions(last_activity_at);
```

### Cleanup Job

Hourly cron to delete expired sessions:
```sql
-- Delete reflection sessions older than 24 hours
DELETE FROM chat_sessions
WHERE session_type = 'reflection'
  AND last_activity_at < NOW() - INTERVAL '24 hours';

-- Delete command sessions older than 30 days
DELETE FROM chat_sessions
WHERE session_type = 'command'
  AND last_activity_at < NOW() - INTERVAL '30 days';
```
(Cascade deletes messages and pending actions)