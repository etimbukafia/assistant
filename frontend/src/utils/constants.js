export const API_BASE_URL = 'http://localhost:8000';

/**
 * Task Status Model:
 * - pending_approval: "Suggested by AI" - needs user approval
 * - approved: Normal actionable task
 * - in_progress: Task being worked on (optional)
 * - completed: Done - hidden inline, visible in history
 * - dismissed: Hidden everywhere
 *
 * Task Types:
 * - explicit: Actionable task
 * - waiting_for: Blocking/dependency task
 */

export const MOCK_MESSAGES = [
    {
        id: 1,
        subject: "Q4 Budget Review",
        sender: "john@company.com",
        recipient: "you@gmail.com",
        summary: "John needs Q4 budget breakdown by Wednesday. Wants to review marketing spend details.",
        body: "Hi,\n\nCould you please send over the Q4 budget breakdown by Wednesday? I specifically want to review the marketing spend details we discussed last week.\n\nThanks,\nJohn",
        needs_reply: true,
        extracted_tasks: ["Send budget breakdown", "Review marketing spend"],
        extracted_dates: ["Wednesday, Dec 22"],
        extracted_people: ["John Doe"],
        extracted_decisions: [],
        received_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
        processed: true,
        tasks: [
            {
                id: 101,
                title: "Send Q4 budget breakdown to John",
                description: "John specifically wants marketing spend details",
                type: "explicit",
                priority: "urgent",
                status: "approved",
                deadline: "Wednesday",
                source_snippet: "Could you please send over the Q4 budget breakdown by Wednesday?",
                confidence: 0.95
            },
            {
                id: 102,
                title: "Review marketing spend details",
                type: "explicit",
                priority: "high",
                status: "pending_approval",
                source_snippet: "I specifically want to review the marketing spend details",
                confidence: 0.88
            }
        ]
    },
    {
        id: 2,
        subject: "Weekly Newsletter",
        sender: "newsletter@tech-news.com",
        recipient: "you@gmail.com",
        summary: "Product updates and team announcements. New features launching next week.",
        body: "Here are the latest updates from the product team...",
        needs_reply: false,
        extracted_tasks: ["Check new feature release date"],
        extracted_dates: [],
        extracted_people: [],
        extracted_decisions: [],
        received_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
        processed: true,
        tasks: []
    },
    {
        id: 3,
        subject: "Meeting Reschedule?",
        sender: "sarah@client.com",
        recipient: "you@gmail.com",
        summary: "Sarah asks if we can move the Tuesday call to Thursday at 2pm.",
        body: "Hey, something came up. Can we move our Tuesday call to Thursday at 2pm instead? I'm waiting for your confirmation.",
        needs_reply: true,
        extracted_tasks: ["Reschedule meeting"],
        extracted_dates: ["Thursday 2pm"],
        extracted_people: ["Sarah Smith"],
        extracted_decisions: [],
        received_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
        processed: true,
        tasks: [
            {
                id: 103,
                title: "Confirm reschedule to Thursday 2pm",
                type: "explicit",
                priority: "high",
                status: "approved",
                deadline: "Thursday 2pm",
                source_snippet: "Can we move our Tuesday call to Thursday at 2pm instead?",
                confidence: 0.92
            },
            {
                id: 104,
                title: "Waiting for confirmation from you",
                type: "waiting_for",
                priority: "normal",
                status: "approved",
                follow_up_condition: "no_reply",
                source_snippet: "I'm waiting for your confirmation.",
                confidence: 0.85
            }
        ]
    },
    {
        id: 4,
        subject: "Project Alpha Update",
        sender: "dev-team@company.com",
        recipient: "you@gmail.com",
        summary: "Development team needs approval on the new API design before proceeding.",
        body: "Hi,\n\nWe've completed the initial API design for Project Alpha. We need your approval before we start implementation. Also, please review the security considerations document attached.\n\nThe deadline for sign-off is Friday EOD.\n\nBest,\nDev Team",
        needs_reply: true,
        extracted_tasks: ["Approve API design", "Review security doc"],
        extracted_dates: ["Friday EOD"],
        extracted_people: ["Dev Team"],
        extracted_decisions: ["API design approval"],
        received_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
        processed: true,
        tasks: [
            {
                id: 105,
                title: "Approve Project Alpha API design",
                type: "explicit",
                priority: "urgent",
                status: "pending_approval",
                deadline: "Friday EOD",
                source_snippet: "We need your approval before we start implementation",
                confidence: 0.94
            },
            {
                id: 106,
                title: "Review security considerations document",
                type: "explicit",
                priority: "high",
                status: "pending_approval",
                source_snippet: "please review the security considerations document attached",
                confidence: 0.91
            },
            {
                id: 107,
                title: "Sign-off on Project Alpha",
                type: "explicit",
                priority: "normal",
                status: "completed",
                deadline: "Friday EOD",
                source_snippet: "The deadline for sign-off is Friday EOD",
                confidence: 0.87
            }
        ]
    }
];

export const MOCK_STATS = {
    total_messages: 45,
    needs_reply_count: 12,
    fyi_only: 33,
    unprocessed: 0,
    has_tasks_count: 8,
    active_tasks: 12,
    waiting_tasks: 4,
    pending_approval_tasks: 3,
    completed_tasks: 5
};
