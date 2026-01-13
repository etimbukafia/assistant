/**
 * Urgency Detection Helpers
 * 
 * UX Rules:
 * - Only tasks with imminent deadlines + high confidence are "urgent"
 * - Visual highlighting only (no sounds, no toasts)
 */

/**
 * Check if a task is urgent (for visual highlighting)
 * 
 * Criteria (ALL must be true):
 * - priority === "urgent"
 * - deadline exists and is within 24 hours
 * - status is actionable (approved or pending_approval)
 * - confidence >= 0.8 (if available)
 */
export const isUrgentTask = (task) => {
    if (!task) return false;

    // Must be urgent priority
    if (task.priority !== 'urgent') return false;

    // Must have actionable status
    if (!['approved', 'pending_approval'].includes(task.status)) return false;

    // Must have deadline within 24 hours
    if (!task.deadline) return false;

    const now = new Date();
    const deadline = new Date(task.deadline);
    const hoursUntil = (deadline - now) / (1000 * 60 * 60);

    if (hoursUntil > 24 || hoursUntil < 0) return false;

    // Confidence check (optional - default to true if not present)
    const confidence = task.deadline_confidence ?? task.confidence ?? 1.0;
    if (confidence < 0.8) return false;

    return true;
};

/**
 * Check if a message has any urgent tasks
 */
export const hasUrgentTasks = (message) => {
    if (!message || !message.tasks || message.tasks.length === 0) return false;
    return message.tasks.some(isUrgentTask);
};

/**
 * Check if message itself is urgent (needs reply from VIP, etc.)
 * Currently returns false - future: check VIP contacts, time-sensitive keywords
 */
export const isUrgentMessage = (message) => {
    // Future: VIP contact check, keyword detection
    return false;
};
