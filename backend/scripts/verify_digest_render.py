
"""
Verify Digest Rendering

Generates sample HTML files for each digest type to verify the design.
"""
import sys
import os
from datetime import datetime, timedelta

# Add services directory to path to import directly
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/app/services'))
import digest_templates as dt
render_digest_email = dt.render_digest_email

def verify_morning_briefing():
    print("Verifying Morning Briefing...")
    content = {
        "generated_at": datetime.now().isoformat(),
        "sections": {
            "urgent_tasks": [
                {"title": "Review Q3 Financials", "priority": "urgent", "deadline": (datetime.now() + timedelta(hours=2)).isoformat()},
                {"title": "Approve New Hire Offer", "priority": "urgent", "deadline": (datetime.now() + timedelta(hours=4)).isoformat()},
            ],
            "due_today": [
                {"title": "Submit Expense Report", "priority": "normal", "deadline": (datetime.now() + timedelta(hours=6)).isoformat()},
            ],
            "threads_needing_reply": [
                {"subject": "Partnership Proposal", "summary": "They are asking for a meeting next week.", "wait_time": "2 days"},
                {"subject": "Project Alpha Status", "summary": "Team needs approval on the new design.", "wait_time": "4 hours"},
            ],
            "today_calendar": [
                {"title": "Management Sync", "start_time": (datetime.now().replace(hour=10, minute=0)).isoformat(), "end_time": (datetime.now().replace(hour=11, minute=0)).isoformat()},
                {"title": "Client Call", "start_time": (datetime.now().replace(hour=14, minute=0)).isoformat(), "end_time": (datetime.now().replace(hour=15, minute=0)).isoformat()},
            ]
        }
    }
    
    html = render_digest_email("morning_briefing", content, "test@example.com")
    
    output_path = "morning_briefing_sample.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {output_path}")
    return output_path

def verify_end_of_day():
    print("Verifying End of Day...")
    content = {
        "generated_at": datetime.now().isoformat(),
        "sections": {
            "completed_today": [
                {"title": "Review Q3 Financials", "priority": "urgent", "completed_at": datetime.now().isoformat()},
                {"title": "Team Standup", "priority": "normal", "completed_at": datetime.now().isoformat()},
            ],
            "still_pending": [
                {"title": "Approve New Hire Offer", "priority": "urgent"},
            ],
            "overdue": [],
            "tomorrow_preview": [
                {"title": "Board Meeting", "start_time": (datetime.now() + timedelta(days=1, hours=9)).isoformat(), "end_time": (datetime.now() + timedelta(days=1, hours=12)).isoformat()},
            ]
        }
    }
    
    html = render_digest_email("end_of_day", content, "test@example.com")
    
    output_path = "end_of_day_sample.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {output_path}")
    return output_path

if __name__ == "__main__":
    verify_morning_briefing()
    verify_end_of_day()
    print("Verification complete.")
