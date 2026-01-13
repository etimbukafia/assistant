import React from 'react';
import { Mail, Reply, Clock } from 'lucide-react';

/**
 * Format a date as relative time (e.g., "3 months ago", "2 weeks ago")
 */
const formatRelativeTime = (dateStr) => {
    if (!dateStr) return null;

    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays < 1) return 'today';
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) {
        const weeks = Math.floor(diffDays / 7);
        return `${weeks} ${weeks === 1 ? 'week' : 'weeks'} ago`;
    }
    if (diffDays < 365) {
        const months = Math.floor(diffDays / 30);
        return `${months} ${months === 1 ? 'month' : 'months'} ago`;
    }
    const years = Math.floor(diffDays / 365);
    return `${years} ${years === 1 ? 'year' : 'years'} ago`;
};

/**
 * ThreadContext - Shows thread history awareness info
 * 
 * Displays:
 * - Message count in thread
 * - When thread started (if > 30 days ago)
 * - When user last replied (if applicable)
 * 
 * Only shown in MessageDetail view to avoid cluttering inbox cards.
 */
const ThreadContext = ({ message }) => {
    if (!message) return null;

    const messageCount = message.thread_message_count || 1;
    const threadStarted = message.thread_started_at;
    const lastReply = message.last_user_reply_at;

    // Only show if there's meaningful context (multi-message thread)
    if (messageCount <= 1 && !lastReply) return null;

    // Calculate if thread is "old" (started > 30 days ago)
    const threadAge = threadStarted ?
        Math.floor((new Date() - new Date(threadStarted)) / (1000 * 60 * 60 * 24)) : 0;
    const isOldThread = threadAge > 30;

    const parts = [];

    // Message count
    if (messageCount > 1) {
        parts.push({
            icon: Mail,
            text: `${messageCount} messages`
        });
    }

    // Thread age (only if old)
    if (isOldThread && threadStarted) {
        parts.push({
            icon: Clock,
            text: `Started ${formatRelativeTime(threadStarted)}`
        });
    }

    // Last user reply
    if (lastReply) {
        parts.push({
            icon: Reply,
            text: `You replied ${formatRelativeTime(lastReply)}`
        });
    }

    if (parts.length === 0) return null;

    return (
        <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 py-2 px-3 bg-gray-50 rounded-lg border border-gray-100">
            {parts.map((part, idx) => (
                <div key={idx} className="flex items-center gap-1">
                    <part.icon className="w-3.5 h-3.5" />
                    <span>{part.text}</span>
                </div>
            ))}
        </div>
    );
};

export default ThreadContext;
