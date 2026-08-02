from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import func

from app.automation.base import BaseAutomationService
from app.automation.catalog import AutomationId
from app.data.models import Message, Task, ThreadState


AUTOMATION_ID: AutomationId = "inbox-copilot"


class InboxCopilotService(BaseAutomationService):
    """Product automation wrapper for inbox triage and drafting."""

    def get_summary(self) -> Dict[str, Any]:
        setting = self._get_or_create_setting(AUTOMATION_ID)
        definition = self._definition(AUTOMATION_ID)
        status = self._status_for(AUTOMATION_ID, setting)
        counts = self._workload_counts()
        return {
            "id": AUTOMATION_ID,
            "name": definition["name"],
            "outcome": definition["outcome"],
            "description": definition["description"],
            "status": status,
            "safety_mode": setting.safety_mode,
            "execution_mode": setting.execution_mode,
            "connectors": self._build_connector_payload(AUTOMATION_ID),
            "degraded_behavior": definition["degraded_behavior"],
            "enabled": bool(setting.enabled),
            "workload": counts,
            "recent_runs": [self._serialize_run(run) for run in self._recent_runs(AUTOMATION_ID)],
        }

    def update(self, *, enabled: Optional[bool] = None) -> Dict[str, Any]:
        setting = self._get_or_create_setting(AUTOMATION_ID)
        if enabled is not None:
            setting.configured = True
            setting.enabled = bool(enabled)
        self.db.add(setting)
        self.db.commit()
        return self.get_summary()

    def run(self, *, trigger: str = "manual") -> Dict[str, Any]:
        counts = self._workload_counts()
        latest_thread = (
            self.db.query(ThreadState)
            .filter(ThreadState.user_id == self.user_id, ThreadState.needs_reply.is_(True))
            .order_by(ThreadState.updated_at.desc())
            .first()
        )
        summary = (
            f"Inbox Copilot found {counts['reply_needed_threads']} reply-needed threads and "
            f"{counts['pending_tasks']} active extracted tasks."
        )
        if latest_thread and latest_thread.subject:
            summary = f"{summary} Next thread: {latest_thread.subject}"

        run = self._record_run(
            automation_id=AUTOMATION_ID,
            status="completed",
            trigger=trigger,
            summary=summary,
            run_metadata={
                "reply_needed_threads": counts["reply_needed_threads"],
                "pending_tasks": counts["pending_tasks"],
                "next_thread_id": latest_thread.thread_id if latest_thread else None,
            },
        )
        self.db.commit()
        return {
            "run": self._serialize_run(run),
            "preview": {
                "reply_needed_threads": counts["reply_needed_threads"],
                "pending_tasks": counts["pending_tasks"],
                "next_thread": {
                    "thread_id": latest_thread.thread_id,
                    "subject": latest_thread.subject,
                    "summary": latest_thread.summary,
                } if latest_thread else None,
            },
        }

    def _workload_counts(self) -> Dict[str, int]:
        reply_needed_threads = (
            self.db.query(func.count(ThreadState.id))
            .filter(ThreadState.user_id == self.user_id, ThreadState.needs_reply.is_(True))
            .scalar()
            or 0
        )
        pending_tasks = (
            self.db.query(func.count(Task.id))
            .filter(
                Task.user_id == self.user_id,
                Task.status.in_(("pending_approval", "approved", "snoozed")),
            )
            .scalar()
            or 0
        )
        unread_messages = (
            self.db.query(func.count(Message.id))
            .filter(Message.user_id == self.user_id, Message.status == "inbox")
            .scalar()
            or 0
        )
        return {
            "reply_needed_threads": int(reply_needed_threads),
            "pending_tasks": int(pending_tasks),
            "inbox_messages": int(unread_messages),
        }

    def _serialize_run(self, run) -> Dict[str, Any]:
        return {
            "id": run.id,
            "status": run.status,
            "trigger": run.trigger,
            "summary": run.summary,
            "run_metadata": run.run_metadata or {},
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }
