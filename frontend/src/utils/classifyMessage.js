/**
 * Classify a message and return applicable chip types.
 * 
 * Chip priority (highest to lowest):
 * 1. urgent - Has urgent tasks with imminent deadlines
 * 2. scheduling - Has scheduling intent
 * 3. needs_reply - Needs a reply (but not urgent)
 * 4. fyi - Informational only (no action needed)
 */
import { hasUrgentTasks } from './urgency';

/**
 * Get classification chips for a message
 * @param {Object} message - Message object from API
 * @returns {string[]} Array of chip types to display
 */
export function classifyMessage(message) {
    if (!message) return [];

    const chips = [];

    // 1. URGENT: Has urgent priority tasks with deadline < 24h
    if (hasUrgentTasks(message)) {
        chips.push('urgent');
    }

    // 2. SCHEDULING: Has scheduling intent detected
    if (message.scheduling_intent) {
        chips.push('scheduling');
    }

    // 3. NEEDS REPLY: needs_reply=true (but not if already marked urgent)
    //    Skip if urgent to avoid redundancy (urgent implies needs attention)
    if (message.needs_reply && !chips.includes('urgent')) {
        chips.push('needs_reply');
    }

    // 4. FYI: No reply needed, no scheduling, no active tasks
    //    This is informational content only
    const hasActiveTasks = (message.tasks || []).some(t =>
        ['pending_approval', 'approved', 'in_progress'].includes(t.status)
    );

    if (!message.needs_reply &&
        !message.scheduling_intent &&
        !hasActiveTasks &&
        chips.length === 0) {
        chips.push('fyi');
    }

    return chips;
}

/**
 * Get the primary (most important) chip for a message
 * @param {Object} message - Message object from API
 * @returns {string|null} Primary chip type or null
 */
export function getPrimaryChip(message) {
    const chips = classifyMessage(message);
    return chips.length > 0 ? chips[0] : null;
}
