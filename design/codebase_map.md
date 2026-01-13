# Donna Codebase Map

A technical reference for the Donna AI Executive Assistant repository.

## 🧠 Backend (Python/FastAPI)
`app/` - Core logic and API.

### Core Logic
- **[main.py](file:///c:/Users/j/afiavana/assistant/app/main.py)**: API Entry point, routes for auth, sync, and messages.
- **[worker.py](file:///c:/Users/j/afiavana/assistant/app/worker.py)**: Background task processor (Redis/Queue).
- **[ai_processor.py](file:///c:/Users/j/afiavana/assistant/app/ai_processor.py)**: Main engine for summarizing and extracting intelligence from emails.
- **[models.py](file:///c:/Users/j/afiavana/assistant/app/models.py)**: SQLAlchemy models (Message, Task, ThreadState, AgentActivityLog).

### Agentic Layer
- **[agents/orchestrator.py](file:///c:/Users/j/afiavana/assistant/app/agents/orchestrator.py)**: The decision-making brain.
- **[agents/modules/](file:///c:/Users/j/afiavana/assistant/app/agents/modules/)**: Stateless capability modules (Communication, Calendar, FollowUp).

### Services
- **[gmail_integration.py](file:///c:/Users/j/afiavana/assistant/app/gmail_integration.py)**: OAuth and Gmail API interactions.
- **[calendar_service.py](file:///c:/Users/j/afiavana/assistant/app/calendar_service.py)**: Scheduling and availability logic.

---

## 🎨 Frontend (React/Vite)
`frontend/` - UI implementation.

### Key Components
- **[App.jsx](file:///c:/Users/j/afiavana/assistant/frontend/src/App.jsx)**: Main routing and state management.
- **[components/FollowUpGenerator.jsx](file:///c:/Users/j/afiavana/assistant/frontend/src/components/FollowUpGenerator.jsx)**: UI for creating/approving follow-ups.
- **[components/SchedulingSuggestionCard.jsx](file:///c:/Users/j/afiavana/assistant/frontend/src/components/SchedulingSuggestionCard.jsx)**: The visual representation of AI-proposed meetings.
- **[views/](file:///c:/Users/j/afiavana/assistant/frontend/src/views/)**: Page-level views (Dashboard, Settings, MessageDetail).

---

## ⚡ Intelligence (Prompts)
`prompts/` - The AI's training and instruction set.

- **[orchestration_decision.md](file:///c:/Users/j/afiavana/assistant/prompts/orchestration_decision.md)**: Logic for when Donna should act autonomously.
- **[extract_tasks_enhanced.md](file:///c:/Users/j/afiavana/assistant/prompts/extract_tasks_enhanced.md)**: Logic for finding commitments in text.
- **[init_thread_state.md](file:///c:/Users/j/afiavana/assistant/prompts/init_thread_state.md)**: Logic for understanding long-term thread context.

---

## 📊 Data Schema Highlights
- **Message**: Raw and processed email data.
- **Task**: Extracted commitments, linked to messages.
- **ThreadState**: The "Memory" of a conversation.
- **AgentActivityLog**: Transparent record of Donna's actions.
