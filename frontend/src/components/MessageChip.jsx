import React from 'react';
import { Zap, Calendar, MessageCircle, Info } from 'lucide-react';

/**
 * Chip configuration for each message classification type
 */
const CHIP_CONFIG = {
    urgent: {
        label: "Urgent",
        bg: "bg-red-100",
        text: "text-red-700",
        border: "border-red-200",
        Icon: Zap
    },
    scheduling: {
        label: "Scheduling",
        bg: "bg-sky-100",
        text: "text-sky-700",
        border: "border-sky-200",
        Icon: Calendar
    },
    needs_reply: {
        label: "Needs reply",
        bg: "bg-amber-100",
        text: "text-amber-700",
        border: "border-amber-200",
        Icon: MessageCircle
    },
    fyi: {
        label: "FYI",
        bg: "bg-gray-100",
        text: "text-gray-600",
        border: "border-gray-200",
        Icon: Info
    }
};

/**
 * MessageChip - Visual classification badge for emails
 * 
 * @param {Object} props
 * @param {string} props.type - Chip type: 'urgent' | 'scheduling' | 'needs_reply' | 'fyi'
 * @param {boolean} props.compact - If true, show only icon (no label)
 */
const MessageChip = ({ type, compact = false }) => {
    const config = CHIP_CONFIG[type];

    if (!config) {
        console.warn(`Unknown chip type: ${type}`);
        return null;
    }

    const { label, bg, text, border, Icon } = config;

    return (
        <span
            className={`
                inline-flex items-center gap-1 
                px-2 py-0.5 
                rounded-full 
                text-xs font-medium
                border
                ${bg} ${text} ${border}
            `}
        >
            <Icon className="w-3 h-3" />
            {!compact && <span>{label}</span>}
        </span>
    );
};

/**
 * MessageChips - Render multiple chips for a message
 * 
 * @param {Object} props
 * @param {string[]} props.chips - Array of chip types to display
 * @param {boolean} props.compact - If true, show only icons
 */
export const MessageChips = ({ chips, compact = false }) => {
    if (!chips || chips.length === 0) return null;

    return (
        <div className="flex flex-wrap gap-1.5">
            {chips.map(type => (
                <MessageChip key={type} type={type} compact={compact} />
            ))}
        </div>
    );
};

export default MessageChip;
