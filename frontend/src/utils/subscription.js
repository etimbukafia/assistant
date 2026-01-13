/**
 * Subscription utilities and constants
 */

export const TIER_NAMES = {
    trial: '7-Day Free Trial',
    pro: 'Pro',
};

export const STATUS_LABELS = {
    trialing: 'Trial Active',
    active: 'Active',
    canceled: 'Canceled',
    past_due: 'Past Due',
    expired: 'Expired',
};

export const PRO_FEATURES = [
    {
        name: 'Unlimited Email Syncs',
        description: 'Sync as many emails as you need',
    },
    {
        name: 'AI Task Extraction',
        description: 'Automatically extract tasks from emails',
    },
    {
        name: 'Scheduling Assistant',
        description: 'AI-powered meeting scheduling',
    },
    {
        name: 'Calendar Integration',
        description: 'Sync with Google Calendar',
    },
    {
        name: 'Daily Digests',
        description: 'Morning briefings and EOD summaries',
    },
];

/**
 * Format remaining trial/subscription time
 * @param {number} daysRemaining - Days remaining
 * @returns {string} Formatted string
 */
export function formatDaysRemaining(daysRemaining) {
    if (daysRemaining === null || daysRemaining === undefined) {
        return '';
    }
    if (daysRemaining <= 0) {
        return 'Expired';
    }
    if (daysRemaining === 1) {
        return '1 day left';
    }
    return `${daysRemaining} days left`;
}

/**
 * Format expiry date for display
 * @param {Date} expiresAt - Expiry date
 * @returns {string} Formatted date string
 */
export function formatExpiryDate(expiresAt) {
    if (!expiresAt) return '';

    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(expiresAt).toLocaleDateString(undefined, options);
}

/**
 * Get urgency level for trial banner styling
 * @param {number} daysRemaining - Days remaining in trial
 * @returns {'low' | 'medium' | 'high'} Urgency level
 */
export function getTrialUrgency(daysRemaining) {
    if (daysRemaining === null || daysRemaining === undefined) {
        return 'low';
    }
    if (daysRemaining <= 1) {
        return 'high';
    }
    if (daysRemaining <= 3) {
        return 'medium';
    }
    return 'low';
}

/**
 * Get status badge color
 * @param {string} status - Subscription status
 * @returns {string} Tailwind color class
 */
export function getStatusColor(status) {
    switch (status) {
        case 'active':
        case 'trialing':
            return 'bg-green-100 text-green-800';
        case 'canceled':
            return 'bg-yellow-100 text-yellow-800';
        case 'past_due':
            return 'bg-orange-100 text-orange-800';
        case 'expired':
            return 'bg-red-100 text-red-800';
        default:
            return 'bg-gray-100 text-gray-800';
    }
}
