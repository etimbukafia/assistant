"""
Digest Service - Generates scheduled digests

Digests aggregate state from ThreadState and Task tables.
No AI processing - just database queries.

Rule: "Messages trigger signals. Threads own state."
Digests read from ThreadState, not Message.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.data.models import Task, ThreadState, CalendarEvent, UserSettings, DailyFocus


class DigestService:
    """
    Service for generating digest content.

    Follows BriefingService pattern - all methods are database queries.
    No LLM calls, no processing - just state aggregation.
    """

    def __init__(self, db: Session, user_email: str):
        self.db = db
        self.user_email = user_email
        self._cached_user_id: Optional[str] = None
        self.user_tz = self._get_user_timezone()

    @property
    def _user_id(self) -> Optional[str]:
        """Cached user_id lookup from UserSettings."""
        if self._cached_user_id is None:
            settings = self.db.query(UserSettings).filter(
                UserSettings.user_email == self.user_email
            ).first()
            self._cached_user_id = settings.user_id if settings else ""
        return self._cached_user_id or None

    def _get_user_timezone(self) -> ZoneInfo:
        """Get user's timezone from settings, default to UTC."""
        settings = self.db.query(UserSettings).filter(
            UserSettings.user_email == self.user_email
        ).first()

        tz_name = settings.default_timezone if settings else "UTC"
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return ZoneInfo("UTC")

    def _get_day_boundaries(self, offset_days: int = 0) -> Tuple[datetime, datetime]:
        """
        Get start and end of a day in user's timezone, converted to UTC.

        Args:
            offset_days: 0 for today, 1 for tomorrow, -1 for yesterday

        Returns:
            Tuple of (day_start_utc, day_end_utc)
        """
        # Current time in user's timezone
        now_user_tz = datetime.now(self.user_tz)

        # Start of the target day in user's timezone
        target_day = now_user_tz.date() + timedelta(days=offset_days)
        day_start_local = datetime.combine(target_day, datetime.min.time(), tzinfo=self.user_tz)
        day_end_local = day_start_local + timedelta(days=1)

        # Convert to UTC for database queries
        day_start_utc = day_start_local.astimezone(timezone.utc)
        day_end_utc = day_end_local.astimezone(timezone.utc)

        return day_start_utc, day_end_utc
    
    def generate_morning_briefing(self) -> Dict[str, Any]:
        """
        Generate morning briefing digest.

        Content:
        - Focus: yesterday's goal recap, weekly target, today's frog
        - Urgent tasks
        - Tasks due today
        - Threads needing reply (from ThreadState - authoritative)
        - Today's calendar preview
        - Pending approval tasks
        """
        now = datetime.now(timezone.utc)
        today_start, today_end = self._get_day_boundaries(offset_days=0)

        sections = {
            "focus": self._get_focus_for_morning(),
            "urgent_tasks": self._get_urgent_tasks(),
            "due_today": self._get_tasks_due_today(),
            "threads_needing_reply": self._get_threads_needing_reply(),
            "today_calendar": self._get_calendar_preview(today_start, today_end),
            "pending_approval": self._get_pending_approval_tasks()
        }

        return {
            "type": "morning_briefing",
            "generated_at": now.isoformat(),
            "sections": sections,
            "stats": {
                "urgent_count": len(sections["urgent_tasks"]),
                "due_today_count": len(sections["due_today"]),
                "threads_needing_reply_count": len(sections["threads_needing_reply"]),
                "events_count": len(sections["today_calendar"]),
                "pending_approval_count": len(sections["pending_approval"])
            }
        }
    
    def generate_end_of_day(self) -> Dict[str, Any]:
        """
        Generate end-of-day summary digest.

        Content:
        - Tasks completed today
        - Still pending tasks
        - Overdue tasks
        - Tomorrow's calendar preview
        """
        now = datetime.now(timezone.utc)
        today_start, _ = self._get_day_boundaries(offset_days=0)
        tomorrow_start, tomorrow_end = self._get_day_boundaries(offset_days=1)

        sections = {
            "focus": self._get_focus_for_end_of_day(),
            "completed_today": self._get_completed_tasks(today_start, now),
            "still_pending": self._get_active_tasks(),
            "overdue": self._get_overdue_tasks(),
            "tomorrow_preview": self._get_calendar_preview(tomorrow_start, tomorrow_end)
        }

        return {
            "type": "end_of_day",
            "generated_at": now.isoformat(),
            "sections": sections,
            "stats": {
                "completed_count": len(sections["completed_today"]),
                "pending_count": len(sections["still_pending"]),
                "overdue_count": len(sections["overdue"]),
                "tomorrow_events_count": len(sections["tomorrow_preview"])
            }
        }
    
    def generate_weekly_review(self) -> Dict[str, Any]:
        """
        Generate weekly follow-up review digest.
        
        Content:
        - Waiting-for tasks
        - Overdue tasks
        - Weekly stats (completed vs created)
        - Stale threads (needs_reply for > 3 days)
        """
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        
        sections = {
            "focus_weekly": self._get_focus_for_weekly_review(week_ago, now),
            "waiting_for": self._get_waiting_for_tasks(),
            "overdue": self._get_overdue_tasks(),
            "weekly_stats": self._get_weekly_stats(week_ago, now),
            "stale_threads": self._get_stale_threads()
        }

        return {
            "type": "weekly_review",
            "generated_at": now.isoformat(),
            "period": {
                "start": week_ago.isoformat(),
                "end": now.isoformat()
            },
            "sections": sections
        }
    
    # =========================================================================
    # Task Queries
    # =========================================================================
    
    def _get_urgent_tasks(self, limit: int = 10) -> List[Dict]:
        """Get urgent priority tasks that are active."""
        tasks = self.db.query(Task).filter(
            Task.priority == "urgent",
            Task.status.in_(["approved", "pending_approval"])
        ).order_by(Task.created_at.desc()).limit(limit).all()
        
        return [self._task_to_dict(t) for t in tasks]
    
    def _get_tasks_due_today(self, limit: int = 20) -> List[Dict]:
        """Get tasks with deadlines today (in user's timezone)."""
        today_start, today_end = self._get_day_boundaries(offset_days=0)

        tasks = self.db.query(Task).filter(
            Task.deadline >= today_start,
            Task.deadline < today_end,
            Task.status.in_(["approved", "pending_approval"])
        ).order_by(Task.deadline.asc()).limit(limit).all()

        return [self._task_to_dict(t) for t in tasks]
    
    def _get_pending_approval_tasks(self, limit: int = 10) -> List[Dict]:
        """Get tasks pending user approval."""
        tasks = self.db.query(Task).filter(
            Task.status == "pending_approval"
        ).order_by(Task.created_at.desc()).limit(limit).all()
        
        return [self._task_to_dict(t) for t in tasks]
    
    def _get_active_tasks(self, limit: int = 20) -> List[Dict]:
        """Get all active (non-completed) tasks."""
        tasks = self.db.query(Task).filter(
            Task.status.in_(["approved", "pending_approval"])
        ).order_by(Task.priority.desc(), Task.created_at.desc()).limit(limit).all()
        
        return [self._task_to_dict(t) for t in tasks]
    
    def _get_completed_tasks(self, since: datetime, until: datetime) -> List[Dict]:
        """Get tasks completed within a time range."""
        tasks = self.db.query(Task).filter(
            Task.status == "completed",
            Task.completed_at >= since,
            Task.completed_at <= until
        ).order_by(Task.completed_at.desc()).all()
        
        return [self._task_to_dict(t) for t in tasks]
    
    def _get_overdue_tasks(self, limit: int = 10) -> List[Dict]:
        """Get tasks past their deadline."""
        now = datetime.now(timezone.utc)
        
        tasks = self.db.query(Task).filter(
            Task.deadline < now,
            Task.status.in_(["approved", "pending_approval"])
        ).order_by(Task.deadline.asc()).limit(limit).all()
        
        return [self._task_to_dict(t) for t in tasks]
    
    def _get_waiting_for_tasks(self, limit: int = 20) -> List[Dict]:
        """Get waiting-for type tasks (awaiting response from others)."""
        tasks = self.db.query(Task).filter(
            Task.task_type == "waiting_for",
            Task.status.in_(["approved", "pending_approval"])
        ).order_by(Task.created_at.desc()).limit(limit).all()
        
        return [self._task_to_dict(t) for t in tasks]
    
    def _task_to_dict(self, task: Task) -> Dict:
        """Convert Task to dictionary for digest."""
        return {
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "status": task.status,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "created_at": task.created_at.isoformat() if task.created_at else None
        }
    
    # =========================================================================
    # Thread Queries (Authoritative Source)
    # =========================================================================
    
    def _get_threads_needing_reply(self, limit: int = 10) -> List[Dict]:
        """
        Get threads that need a reply.
        
        IMPORTANT: This queries ThreadState.needs_reply (authoritative)
        NOT Message.needs_reply (signal only).
        """
        threads = self.db.query(ThreadState).filter(
            ThreadState.needs_reply == True
        ).order_by(ThreadState.updated_at.desc()).limit(limit).all()
        
        return [self._thread_to_dict(t) for t in threads]
    
    def _get_stale_threads(self, days: int = 3, limit: int = 10) -> List[Dict]:
        """Get threads needing reply for more than X days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        threads = self.db.query(ThreadState).filter(
            ThreadState.needs_reply == True,
            ThreadState.updated_at < cutoff
        ).order_by(ThreadState.updated_at.asc()).limit(limit).all()
        
        return [self._thread_to_dict(t) for t in threads]
    
    def _thread_to_dict(self, thread: ThreadState) -> Dict:
        """Convert ThreadState to dictionary for digest."""
        return {
            "thread_id": thread.thread_id,
            "subject": thread.subject,
            "summary": thread.summary,
            "last_action": thread.last_action,
            "last_action_by": thread.last_action_by,
            "updated_at": thread.updated_at.isoformat() if thread.updated_at else None
        }
    
    # =========================================================================
    # Calendar Queries
    # =========================================================================
    
    def _get_calendar_preview(self, start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
        """Get calendar events in a time range."""
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.start_time >= start,
            CalendarEvent.start_time < end,
            CalendarEvent.status.in_(["upcoming", "created"])
        ).order_by(CalendarEvent.start_time.asc()).limit(limit).all()
        
        return [self._event_to_dict(e) for e in events]
    
    def _event_to_dict(self, event: CalendarEvent) -> Dict:
        """Convert CalendarEvent to dictionary for digest."""
        return {
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time.isoformat() if event.start_time else None,
            "end_time": event.end_time.isoformat() if event.end_time else None,
            "participants": event.participants or []
        }
    
    # =========================================================================
    # Focus / Daily Goals Queries
    # =========================================================================

    def _get_focus_for_date(self, target_date) -> Optional[Dict]:
        """Get DailyFocus row for a specific date."""
        if not self._user_id:
            return None

        row = self.db.query(DailyFocus).filter(
            DailyFocus.user_id == self._user_id,
            DailyFocus.focus_date == target_date,
        ).first()
        if not row:
            return None

        goals = row.goals or []
        completed = sum(1 for g in goals if g.get("completed"))
        frog_title = None
        frog_completed = False
        if row.frog_task_id:
            frog = self.db.query(Task).filter(Task.id == row.frog_task_id).first()
            if frog:
                frog_title = frog.title
                frog_completed = frog.status == "completed"

        return {
            "goals": goals,
            "goals_total": len(goals),
            "goals_completed": completed,
            "weekly_target": row.weekly_target,
            "frog_task_title": frog_title,
            "frog_completed": frog_completed,
        }

    def _get_focus_for_morning(self) -> Optional[Dict]:
        """
        Morning briefing focus data:
        - Yesterday's goal recap
        - Weekly target reminder
        - Today's frog (if already set)
        """
        now_user = datetime.now(self.user_tz)
        yesterday = now_user.date() - timedelta(days=1)
        today = now_user.date()

        yesterday_focus = self._get_focus_for_date(yesterday)
        today_focus = self._get_focus_for_date(today)

        result = {}
        if yesterday_focus:
            result["yesterday_goals_completed"] = yesterday_focus["goals_completed"]
            result["yesterday_goals_total"] = yesterday_focus["goals_total"]
        if today_focus:
            result["weekly_target"] = today_focus.get("weekly_target")
            result["frog_task_title"] = today_focus.get("frog_task_title")
        elif yesterday_focus:
            result["weekly_target"] = yesterday_focus.get("weekly_target")

        return result if result else None

    def _get_focus_for_end_of_day(self) -> Optional[Dict]:
        """
        End-of-day focus data:
        - Today's goal progress
        - Whether frog was tackled
        """
        now_user = datetime.now(self.user_tz)
        today = now_user.date()
        focus = self._get_focus_for_date(today)
        if not focus:
            return None

        frog_completed = focus.get("frog_completed", False)

        return {
            "goals_completed": focus["goals_completed"],
            "goals_total": focus["goals_total"],
            "frog_task_title": focus.get("frog_task_title"),
            "frog_completed": frog_completed,
        }

    def _get_focus_for_weekly_review(self, start: datetime, end: datetime) -> Optional[Dict]:
        """
        Weekly review focus data:
        - Total goals set vs completed across the week
        - Weekly target text
        """
        if not self._user_id:
            return None

        rows = self.db.query(DailyFocus).filter(
            DailyFocus.user_id == self._user_id,
            DailyFocus.focus_date >= start.date(),
            DailyFocus.focus_date <= end.date(),
        ).all()

        if not rows:
            return None

        total_set = 0
        total_completed = 0
        weekly_target = None
        for row in rows:
            goals = row.goals or []
            total_set += len(goals)
            total_completed += sum(1 for g in goals if g.get("completed"))
            if row.weekly_target:
                weekly_target = row.weekly_target

        return {
            "goals_set": total_set,
            "goals_completed": total_completed,
            "weekly_target": weekly_target,
        }

    # =========================================================================
    # Stats Queries
    # =========================================================================
    
    def _get_weekly_stats(self, start: datetime, end: datetime) -> Dict:
        """Get task statistics for a time period."""
        completed = self.db.query(Task).filter(
            Task.completed_at >= start,
            Task.completed_at <= end
        ).count()
        
        created = self.db.query(Task).filter(
            Task.created_at >= start,
            Task.created_at <= end
        ).count()
        
        dismissed = self.db.query(Task).filter(
            Task.dismissed_at >= start,
            Task.dismissed_at <= end
        ).count()
        
        return {
            "completed": completed,
            "created": created,
            "dismissed": dismissed,
            "net_change": created - completed - dismissed
        }
