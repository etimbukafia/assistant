"""
Sample emails for testing LLM orchestrator.
Realistic emails an executive assistant would handle.
"""

EMAILS = [
    # 1. Meeting scheduling request
    {
        "id": "meeting_request",
        "sender": "john.martinez@acmecorp.com",
        "subject": "Q1 Strategy Review - Need to Schedule",
        "body": """Hi,

I hope this finds you well. We need to schedule the Q1 strategy review meeting with the executive team.

Could you check David's availability for next week? We're looking at either Tuesday afternoon or Thursday morning. The meeting should be about 2 hours.

Also, please book the large conference room on the 5th floor if available.

Let me know what works.

Best,
John Martinez
VP of Operations"""
    },

    # 2. Urgent request with deadline
    {
        "id": "urgent_deadline",
        "sender": "sarah.chen@investors.com",
        "subject": "URGENT: Board Materials Needed by Friday 5PM",
        "body": """Hi,

The board meeting has been moved up to Monday morning. We urgently need the following materials by Friday at 5pm EST:

1. Updated financial projections for Q2-Q4
2. The revised org chart with the new hires
3. Summary of the pending litigation matter (ask Legal)

This is critical - the board chair specifically requested these items. Please confirm receipt and let me know if there are any issues getting these together.

Sarah Chen
Investor Relations"""
    },

    # 3. FYI/Newsletter (no reply needed)
    {
        "id": "newsletter_fyi",
        "sender": "hr@company.com",
        "subject": "Company Newsletter - January Edition",
        "body": """Dear Team,

Happy New Year! Here's what's happening at the company this month:

ANNOUNCEMENTS:
- Office will be closed January 15th for MLK Day
- New coffee machines installed on floors 3 and 5
- Reminder: Complete your annual compliance training by Jan 31

EMPLOYEE SPOTLIGHT:
Congratulations to Maria Garcia on her 10-year anniversary!

UPCOMING EVENTS:
- Jan 20: Town Hall Meeting (3pm, Main Auditorium)
- Jan 25: Team Building Event (signup required)

Best regards,
HR Team"""
    },

    # 4. Travel coordination
    {
        "id": "travel_coordination",
        "sender": "michael.okonkwo@partner.org",
        "subject": "Re: London Trip - Flight and Hotel Details",
        "body": """Hi,

Thanks for coordinating David's London trip next month. Here are the details from our side:

The conference runs February 15-17 at the Hilton Park Lane. I've arranged for David to speak on the 16th at 2pm (45 min slot).

A few requests:
- Can you book his flights to arrive by the 14th evening? He'll need time to prep.
- The dinner with Lord Ashworth is confirmed for the 15th at 7pm at The Ivy
- Please send me his dietary restrictions for the conference dinner

I've cc'd my assistant James who can help with ground transportation.

Looking forward to seeing David there!

Michael Okonkwo
Director of Partnerships"""
    },

    # 5. Complex multi-part request
    {
        "id": "complex_request",
        "sender": "cfo@company.com",
        "subject": "Several Items - EOD Today",
        "body": """Hi,

Quick items before I head into back-to-back meetings:

1. EXPENSES: I submitted my Tokyo trip expenses last week - can you check if Finance has processed them? Receipt for the client dinner might be missing.

2. CALENDAR: Block off March 3-7 as tentative - potential acquisition meetings. Don't tell anyone about this yet.

3. SIGNATURES: The Henderson contract is on my desk - I've signed it. Please scan and send to Legal, then FedEx the original to their NYC office (address in the file).

4. REMINDER: Did we ever hear back from McKinsey about the consulting proposal? If not, ping them.

5. PERSONAL: My daughter's recital is Thursday at 6pm - make sure nothing gets scheduled after 4:30 that day.

Thanks,
Robert

P.S. - Order lunch for the 2pm meeting, 6 people, usual place."""
    },
]


def get_email(email_id: str) -> dict:
    """Get a specific email by ID."""
    for email in EMAILS:
        if email["id"] == email_id:
            return email
    raise ValueError(f"Email not found: {email_id}")


def get_all_emails() -> list:
    """Get all test emails."""
    return EMAILS
