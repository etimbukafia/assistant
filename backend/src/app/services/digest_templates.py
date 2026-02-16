"""
Digest Templates - HTML Email Rendering

Renders "Boutique Stationery" styled emails for:
- Morning Briefing
- End of Day
- Weekly Review

Design System:
- Background: #F9F6F2 (Linen)
- Header/Accent: #7E2E2E (Rich Auburn)
- Text: #050505 (Obsidian)
- Cards: #FFFFFF (White) with Accent Borders
"""
from typing import Dict, Any, List
from datetime import datetime

# =============================================================================
# Constants & Styles
# =============================================================================

COLORS = {
    "linen": "#F9F6F2",
    "auburn": "#7E2E2E",
    "copper": "#D97745",
    "sage": "#8A9A5B",
    "burgundy": "#800020",
    "obsidian": "#050505",
    "white": "#FFFFFF",
    "gray_light": "#E5E7EB",
    "gray_text": "#6B7280"
}

# Base styles for inline CSS
STYLES = {
    "body": f"background-color: {COLORS['linen']}; margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;",
    "container": "max-width: 600px; margin: 0 auto; padding: 20px;",
    "header": "text-align: center; padding: 30px 0 20px;",
    "brand": f"font-size: 24px; font-weight: bold; color: {COLORS['auburn']}; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px;",
    "title": f"font-size: 32px; font-family: 'Georgia', 'Times New Roman', serif; color: {COLORS['obsidian']}; margin: 0;",
    "card": f"background-color: {COLORS['white']}; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);",
    "section_title": f"font-size: 14px; font-weight: bold; color: {COLORS['auburn']}; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 16px;",
    "text": f"font-size: 16px; line-height: 1.5; color: {COLORS['obsidian']};",
    "text_muted": f"font-size: 14px; color: {COLORS['gray_text']};",
    "list_item": f"padding: 12px 0; border-bottom: 1px solid {COLORS['gray_light']};",
    "footer": f"text-align: center; padding: 40px 0; color: {COLORS['gray_text']}; font-size: 12px;",
    "link": f"color: {COLORS['auburn']}; text-decoration: none;",
    "button": f"display: inline-block; background-color: {COLORS['auburn']}; color: {COLORS['white']}; padding: 12px 24px; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 14px;"
}

def _get_greeting() -> str:
    """Get time-appropriate greeting."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning,"
    elif hour < 18:
        return "Good afternoon,"
    else:
        return "Good evening,"

# =============================================================================
# Component Renderers
# =============================================================================

def _render_stat_pill(label: str, count: int, is_urgent: bool = False) -> str:
    """Render a small stat pill/badge."""
    bg = COLORS['burgundy'] if is_urgent else COLORS['gray_light']
    text_col = COLORS['white'] if is_urgent else COLORS['obsidian']
    return f"""
    <div style="display: inline-block; margin-right: 12px; margin-bottom: 8px;">
        <span style="font-size: 20px; font-weight: bold; color: {COLORS['obsidian']}; margin-right: 4px;">{count}</span>
        <span style="font-size: 12px; color: {COLORS['gray_text']}; text-transform: uppercase;">{label}</span>
    </div>
    """

def _render_task_item(task: Dict[str, Any]) -> str:
    """Render a single task list item."""
    priority_marker = ""
    if task.get("priority") == "urgent":
        priority_marker = f'<span style="display: inline-block; width: 8px; height: 8px; background-color: {COLORS["burgundy"]}; border-radius: 50%; margin-right: 8px;"></span>'
    
    deadline = ""
    if task.get("deadline"):
        dt = datetime.fromisoformat(task["deadline"])
        deadline = f'<div style="font-size: 12px; color: {COLORS["gray_text"]}; margin-top: 4px;">Due by {dt.strftime("%I:%M %p")}</div>'

    return f"""
    <div style="{STYLES['list_item']}">
        <div style="display: flex; align-items: flex-start;">
            <div style="flex-grow: 1;">
                <div style="font-size: 16px; color: {COLORS['obsidian']}; font-weight: 500;">
                    {priority_marker}{task['title']}
                </div>
                {deadline}
            </div>
        </div>
    </div>
    """

def _render_event_item(event: Dict[str, Any]) -> str:
    """Render a calendar event item."""
    start_dt = datetime.fromisoformat(event["start_time"])
    end_dt = datetime.fromisoformat(event["end_time"])
    
    return f"""
    <div style="{STYLES['list_item']}">
        <div style="display: flex;">
            <div style="min-width: 80px; font-size: 14px; font-weight: bold; color: {COLORS['auburn']};">
                {start_dt.strftime("%I:%M")}
            </div>
            <div>
                <div style="font-size: 16px; font-weight: 500; color: {COLORS['obsidian']};">
                    {event['title']}
                </div>
                <div style="font-size: 12px; color: {COLORS['gray_text']}; margin-top: 2px;">
                    {start_dt.strftime("%I:%M %p")} - {end_dt.strftime("%I:%M %p")}
                </div>
            </div>
        </div>
    </div>
    """

def _render_thread_item(thread: Dict[str, Any]) -> str:
    """Render a thread item."""
    return f"""
    <div style="{STYLES['list_item']}">
        <div style="font-size: 16px; font-weight: 500; color: {COLORS['obsidian']}; margin-bottom: 4px;">
            {thread['subject']}
        </div>
        <div style="font-size: 14px; color: {COLORS['gray_text']}; line-height: 1.4;">
            {thread.get('summary', 'No summary available.')}
        </div>
        <div style="font-size: 12px; color: {COLORS['auburn']}; margin-top: 6px; font-weight: 500;">
            Wait time: {thread.get('wait_time', 'Action needed')}
        </div>
    </div>
    """

def _render_focus_morning(focus: Dict[str, Any]) -> str:
    """Render focus section for morning briefing."""
    if not focus:
        return ""

    parts = []

    # Yesterday's recap
    yt = focus.get("yesterday_goals_total", 0)
    yc = focus.get("yesterday_goals_completed", 0)
    if yt > 0:
        emoji = "\u2705" if yc == yt else "\u2B50" if yc > 0 else "\u23F3"
        parts.append(f'<div style="font-size: 15px; color: {COLORS["obsidian"]}; margin-bottom: 8px;">{emoji} Yesterday: {yc}/{yt} goals completed</div>')

    # Weekly target
    wt = focus.get("weekly_target")
    if wt:
        parts.append(f'<div style="font-size: 14px; color: {COLORS["copper"]}; margin-bottom: 8px;">\U0001F3AF Weekly target: {wt}</div>')

    # Today's frog
    frog = focus.get("frog_task_title")
    if frog:
        parts.append(f'<div style="font-size: 14px; color: {COLORS["auburn"]}; font-weight: 600; margin-bottom: 4px;">\u26A1 Eat the frog: {frog}</div>')

    if not parts:
        return ""

    content = "".join(parts)
    return f"""
    <div style="{STYLES['card']} border-left: 4px solid {COLORS['copper']}; padding: 16px 24px;">
        <h3 style="{STYLES['section_title']} color: {COLORS['copper']};">Your Focus</h3>
        {content}
    </div>
    """


def _render_focus_end_of_day(focus: Dict[str, Any]) -> str:
    """Render focus section for end-of-day digest."""
    if not focus:
        return ""

    parts = []

    gt = focus.get("goals_total", 0)
    gc = focus.get("goals_completed", 0)
    if gt > 0:
        pct = int((gc / gt) * 100) if gt else 0
        bar_color = COLORS["sage"] if pct >= 66 else COLORS["copper"] if pct >= 33 else COLORS["gray_text"]
        parts.append(f'''
        <div style="margin-bottom: 12px;">
            <div style="font-size: 15px; color: {COLORS["obsidian"]}; margin-bottom: 6px;">Goals: {gc}/{gt} completed</div>
            <div style="background: {COLORS["gray_light"]}; border-radius: 4px; height: 8px; overflow: hidden;">
                <div style="background: {bar_color}; height: 100%; width: {pct}%; border-radius: 4px;"></div>
            </div>
        </div>''')

    frog = focus.get("frog_task_title")
    if frog:
        done = focus.get("frog_completed", False)
        icon = "\u2705" if done else "\u23F3"
        label = "Completed!" if done else "Not completed"
        parts.append(f'<div style="font-size: 14px; color: {COLORS["auburn"]};">{icon} Frog ({frog}): {label}</div>')

    if not parts:
        return ""

    content = "".join(parts)
    return f"""
    <div style="{STYLES['card']} border-left: 4px solid {COLORS['copper']}; padding: 16px 24px;">
        <h3 style="{STYLES['section_title']} color: {COLORS['copper']};">Today's Focus Recap</h3>
        {content}
    </div>
    """


def _render_focus_weekly(focus: Dict[str, Any]) -> str:
    """Render focus section for weekly review."""
    if not focus:
        return ""

    parts = []

    gs = focus.get("goals_set", 0)
    gc = focus.get("goals_completed", 0)
    if gs > 0:
        pct = int((gc / gs) * 100)
        parts.append(f'<div style="font-size: 15px; color: {COLORS["obsidian"]}; margin-bottom: 8px;">\U0001F4CA Weekly goals: {gc}/{gs} completed ({pct}%)</div>')

    wt = focus.get("weekly_target")
    if wt:
        parts.append(f'<div style="font-size: 14px; color: {COLORS["copper"]};">\U0001F3AF Target: {wt}</div>')

    if not parts:
        return ""

    content = "".join(parts)
    return f"""
    <div style="{STYLES['card']} border-left: 4px solid {COLORS['copper']}; padding: 16px 24px;">
        <h3 style="{STYLES['section_title']} color: {COLORS['copper']};">Focus Performance</h3>
        {content}
    </div>
    """


def _render_section(title: str, items: List[str], empty_msg: str = "Nothing to show.") -> str:
    """Render a generic card section."""
    if not items:
        content = f'<div style="font-style: italic; color: {COLORS["gray_text"]}; padding: 10px 0;">{empty_msg}</div>'
    else:
        content = "".join(items)
        
    return f"""
    <div style="{STYLES['card']}">
        <h3 style="{STYLES['section_title']}">{title}</h3>
        {content}
    </div>
    """

# =============================================================================
# Main Renderers
# =============================================================================

def _render_morning_briefing(content: Dict[str, Any]) -> str:
    sections = content.get("sections", {})

    # Overview (Top Card)
    urgent_count = len(sections.get("urgent_tasks", []))
    event_count = len(sections.get("today_calendar", []))
    thread_count = len(sections.get("threads_needing_reply", []))

    stats_html = f"""
    <div style="{STYLES['card']} border-left: 4px solid {COLORS['auburn']};">
        <p style="{STYLES['text']} margin-bottom: 16px;">
            {_get_greeting()} Here is your briefing for today.
        </p>
        <div>
            {_render_stat_pill("Urgent", urgent_count, is_urgent=True) if urgent_count else ""}
            {_render_stat_pill("Events", event_count)}
            {_render_stat_pill("Replies", thread_count)}
        </div>
    </div>
    """

    # Focus section (yesterday recap, weekly target, frog)
    focus_html = _render_focus_morning(sections.get("focus") or {})

    # 1. Urgent Tasks
    urgent_tasks = [_render_task_item(t) for t in sections.get("urgent_tasks", [])]
    urgent_html = _render_section("Urgent Attention", urgent_tasks) if urgent_tasks else ""

    # 2. Schedule
    events = [_render_event_item(e) for e in sections.get("today_calendar", [])]
    schedule_html = _render_section("Today's Schedule", events, "No meetings scheduled.")

    # 3. Threads
    threads = [_render_thread_item(t) for t in sections.get("threads_needing_reply", [])]
    threads_html = _render_section("Needing Reply", threads) if threads else ""

    # 4. Due Today
    due_tasks = [_render_task_item(t) for t in sections.get("due_today", [])]
    due_html = _render_section("Tasks Due Today", due_tasks) if due_tasks else ""

    return f"{stats_html}{focus_html}{urgent_html}{schedule_html}{threads_html}{due_html}"

def _render_end_of_day(content: Dict[str, Any]) -> str:
    sections = content.get("sections", {})
    
    # Stats
    completed_count = len(sections.get("completed_today", []))
    pending_count = len(sections.get("still_pending", []))
    overdue_count = len(sections.get("overdue", []))
    
    stats_html = f"""
    <div style="{STYLES['card']} border-left: 4px solid {COLORS['auburn']};">
        <p style="{STYLES['text']} margin-bottom: 16px;">
            {_get_greeting()} Here is your end of day summary.
        </p>
        <div>
            {_render_stat_pill("Completed", completed_count)}
            {_render_stat_pill("Pending", pending_count)}
            {_render_stat_pill("Overdue", overdue_count, is_urgent=True) if overdue_count else ""}
        </div>
    </div>
    """
    
    # Focus section (today's goal progress, frog status)
    focus_html = _render_focus_end_of_day(sections.get("focus") or {})

    # 1. Completed
    completed = [_render_task_item(t) for t in sections.get("completed_today", [])]
    completed_html = _render_section("Completed Today", completed, "No tasks completed yet.")

    # 2. Tomorrow Preview
    events = [_render_event_item(e) for e in sections.get("tomorrow_preview", [])]
    tomorrow_html = _render_section("Tomorrow's Schedule", events, "No meetings scheduled.")

    return f"{stats_html}{focus_html}{completed_html}{tomorrow_html}"

def _render_weekly_review(content: Dict[str, Any]) -> str:
    sections = content.get("sections", {})
    stats = sections.get("weekly_stats", {})
    
    stats_html = f"""
    <div style="{STYLES['card']} border-left: 4px solid {COLORS['auburn']};">
        <p style="{STYLES['text']} margin-bottom: 16px;">
            Your weekly performance review.
        </p>
        <div>
            {_render_stat_pill("Completed", stats.get("completed", 0))}
            {_render_stat_pill("Created", stats.get("created", 0))}
            {_render_stat_pill("Net", stats.get("net_change", 0))}
        </div>
    </div>
    """
    
    # Focus performance (goals completed this week, weekly target)
    focus_html = _render_focus_weekly(sections.get("focus_weekly") or {})

    # 1. Waiting For
    waiting = [_render_task_item(t) for t in sections.get("waiting_for", [])]
    waiting_html = _render_section("Waiting For", waiting)

    # 2. Stale Threads
    threads = [_render_thread_item(t) for t in sections.get("stale_threads", [])]
    threads_html = _render_section("Stale Conversations", threads)

    return f"{stats_html}{focus_html}{waiting_html}{threads_html}"

# =============================================================================
# Public Interface
# =============================================================================

def render_digest_email(digest_type: str, content: Dict[str, Any], user_email: str) -> str:
    """
    Render HTML email for a digest.
    
    Args:
        digest_type: morning_briefing | end_of_day | weekly_review
        content: Digest content dictionary
        user_email: Recipient email
        
    Returns:
        Rendered HTML string
    """
    if digest_type == "morning_briefing":
        title = "Morning Briefing"
        body_content = _render_morning_briefing(content)
    elif digest_type == "end_of_day":
        title = "End of Day"
        body_content = _render_end_of_day(content)
    elif digest_type == "weekly_review":
        title = "Weekly Review"
        body_content = _render_weekly_review(content)
    else:
        title = "Digest"
        body_content = "<p>Here is your digest.</p>"

    # Wrap in main layout
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Donna</title>
    </head>
    <body style="{STYLES['body']}">
        <div style="{STYLES['container']}">
            <!-- Header -->
            <div style="{STYLES['header']}">
                <div style="{STYLES['brand']}">DONNA</div>
                <h1 style="{STYLES['title']}">{title}</h1>
                <div style="font-size: 14px; color: {COLORS['copper']}; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px;">
                    {datetime.now().strftime("%A, %B %d")}
                </div>
            </div>
            
            <!-- Content -->
            {body_content}
            
            <!-- Footer -->
            <div style="{STYLES['footer']}">
                <p>
                    Sent by <strong>Donna</strong><br>
                    Your Executive Assistant
                </p>
                <p style="margin-top: 20px;">
                    <a href="#" style="{STYLES['link']}">Manage Preferences</a>
                    &nbsp;|&nbsp;
                    <a href="#" style="{STYLES['link']}">Unsubscribe</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
