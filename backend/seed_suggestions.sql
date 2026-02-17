-- Seed 3 fake emails with scheduling intent for end-to-end testing.
-- The worker will pick these up, process them with AI, and generate scheduling suggestions.

INSERT INTO messages (
    message_id, thread_id, user_id, subject, sender, recipient,
    body, received_at, processed, status, created_at, updated_at
) VALUES
(
    'seed-sched-msg-1',
    'seed-sched-thread-1',
    '638d5015-d56a-4555-9da4-cf7f2315ab1c',
    'Product Demo This Week?',
    'sarah@techventures.com',
    'you@company.com',
    'Hi there,

We''ve been evaluating a few tools and your product came up in our research. Could we schedule a product demo sometime this week? Ideally 60 minutes so we can do a deep dive.

Mike from our engineering team would also join. We''re flexible on timing but prefer mornings if possible.

Looking forward to it!
Sarah Chen
VP of Product, TechVentures',
    NOW(),
    false,
    'inbox',
    NOW(),
    NOW()
),
(
    'seed-sched-msg-2',
    'seed-sched-thread-2',
    '638d5015-d56a-4555-9da4-cf7f2315ab1c',
    'Re: Infrastructure Migration',
    'daniel@company.com',
    'you@company.com',
    'Hey,

Can we hop on a quick 30-min call to discuss the infrastructure migration plan? I have some concerns about the timeline and want to align before the board meeting next week.

Free anytime Wednesday or Thursday afternoon.

Thanks,
Daniel',
    NOW(),
    false,
    'inbox',
    NOW(),
    NOW()
),
(
    'seed-sched-msg-3',
    'seed-sched-thread-3',
    '638d5015-d56a-4555-9da4-cf7f2315ab1c',
    'Re: Interview Panel - Reschedule Needed',
    'john@acmecorp.com',
    'you@company.com',
    'Hi,

Unfortunately we need to reschedule Friday''s interview panel. Rachel has a conflict that just came up. Could we find a new 90-minute slot next week?

Rachel and I would both be joining from the Acme side. Lisa from your team confirmed she''s flexible.

Apologies for the last-minute change.

Best,
John Miller
Head of Talent, Acme Corp',
    NOW(),
    false,
    'inbox',
    NOW(),
    NOW()
);

-- Enqueue process_email tasks so the worker picks them up
INSERT INTO task_queue (task_type, user_id, payload, status, scheduled_for, created_at)
SELECT
    'process_email',
    '638d5015-d56a-4555-9da4-cf7f2315ab1c',
    json_build_object('message_id', id, 'user_id', '638d5015-d56a-4555-9da4-cf7f2315ab1c'),
    'pending',
    NOW(),
    NOW()
FROM messages
WHERE message_id IN ('seed-sched-msg-1', 'seed-sched-msg-2', 'seed-sched-msg-3');
