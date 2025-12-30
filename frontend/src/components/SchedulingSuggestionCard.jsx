import React, { useState } from 'react';
import { Calendar, Clock, Users, Send, X, AlertTriangle, Edit2, Check, RefreshCw } from 'lucide-react';
import { timeAgo } from '../utils/helpers';

/**
 * SchedulingSuggestionCard
 *
 * Displays scheduling suggestions detected from message content.
 * Shows suggested time slots, draft reply, and action buttons.
 *
 * Props:
 * - suggestion: The scheduling suggestion object from API
 * - onSend: Callback when user approves and sends availability reply
 * - onDismiss: Callback when user dismisses the suggestion
 * - onCreateEvent: Callback when user confirms and creates calendar event
 */
const SchedulingSuggestionCard = ({
    suggestion,
    onSend,
    onDismiss,
    onCreateEvent,
    onRefresh,
    isLoading = false,
    isRefreshing = false
}) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editedReply, setEditedReply] = useState(suggestion?.draft_reply || '');
    const [selectedSlotIndex, setSelectedSlotIndex] = useState(0);

    if (!suggestion) return null;

    const {
        meeting_type,
        participants,
        suggested_slots,
        duration_minutes,
        timezone,
        draft_reply,
        status,
        created_at
    } = suggestion;

    // Format time slot for display
    const formatSlot = (slot) => {
        const start = new Date(slot.start_time);
        const options = { weekday: 'short', hour: 'numeric', minute: '2-digit' };
        return start.toLocaleString('en-US', options);
    };

    // Get timezone abbreviation
    const tzDisplay = timezone?.split('/').pop()?.replace('_', ' ') || timezone || 'UTC';

    // Meeting type badge colors
    const typeColors = {
        call: 'bg-blue-100 text-blue-700',
        review: 'bg-purple-100 text-purple-700',
        demo: 'bg-green-100 text-green-700',
        coffee: 'bg-amber-100 text-amber-700',
        interview: 'bg-indigo-100 text-indigo-700',
        other: 'bg-gray-100 text-gray-700'
    };

    const handleSend = () => {
        onSend?.(suggestion.id, isEditing ? editedReply : null);
        setIsEditing(false);
    };

    const handleCreateEvent = () => {
        onCreateEvent?.(suggestion.id, selectedSlotIndex);
    };

    // Don't show if already sent/dismissed/accepted
    if (status === 'sent' || status === 'dismissed' || status === 'accepted') {
        return null;
    }

    return (
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-4 mt-3">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-blue-600" />
                    <span className="text-xs font-semibold text-blue-800 uppercase tracking-wide">
                        Scheduling Detected
                    </span>
                    {created_at && (
                        <span className="text-xs text-gray-400">
                            · {timeAgo(created_at)}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => onRefresh?.(suggestion.message_id)}
                        disabled={isRefreshing}
                        className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 disabled:opacity-50"
                        title="Refresh with latest availability"
                    >
                        <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`} />
                        {isRefreshing ? 'Refreshing...' : 'Refresh'}
                    </button>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColors[meeting_type] || typeColors.other}`}>
                        {meeting_type}
                    </span>
                </div>
            </div>

            {/* Meeting Details */}
            <div className="flex flex-wrap gap-3 mb-3 text-sm text-gray-600">
                {participants?.length > 0 && (
                    <div className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5" />
                        <span>{participants.slice(0, 2).map(p => p.split('@')[0]).join(', ')}</span>
                        {participants.length > 2 && <span className="text-gray-400">+{participants.length - 2}</span>}
                    </div>
                )}
                <div className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{duration_minutes} min</span>
                </div>
            </div>

            {/* Suggested Time Slots */}
            {suggested_slots?.length > 0 && (
                <div className="mb-3">
                    <div className="text-xs font-medium text-gray-500 mb-2">Suggested Times ({tzDisplay})</div>
                    <div className="flex flex-wrap gap-2">
                        {suggested_slots.map((slot, idx) => (
                            <button
                                key={idx}
                                onClick={() => setSelectedSlotIndex(idx)}
                                className={`
                                    px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                                    ${selectedSlotIndex === idx
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-white border border-gray-200 text-gray-700 hover:border-blue-300'
                                    }
                                    ${slot.has_conflict ? 'ring-2 ring-amber-400' : ''}
                                `}
                            >
                                {formatSlot(slot)}
                                {slot.has_conflict && (
                                    <AlertTriangle className="w-3 h-3 ml-1 inline text-amber-500" />
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Conflict Warning */}
                    {suggested_slots[selectedSlotIndex]?.has_conflict && (
                        <div className="mt-2 flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
                            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div className="text-xs text-amber-800">
                                <span className="font-medium">Conflict detected:</span>{' '}
                                {suggested_slots[selectedSlotIndex].conflict_details || 'This time overlaps with an existing event'}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Draft Reply */}
            <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                    <div className="text-xs font-medium text-gray-500">Draft Reply</div>
                    <button
                        onClick={() => setIsEditing(!isEditing)}
                        className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                    >
                        {isEditing ? <Check className="w-3 h-3" /> : <Edit2 className="w-3 h-3" />}
                        {isEditing ? 'Done' : 'Edit'}
                    </button>
                </div>
                {isEditing ? (
                    <textarea
                        value={editedReply}
                        onChange={(e) => setEditedReply(e.target.value)}
                        className="w-full p-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                        rows={2}
                    />
                ) : (
                    <div className="text-sm text-gray-700 bg-white p-2 rounded-lg border border-gray-100">
                        "{draft_reply}"
                    </div>
                )}
            </div>

            {/* Actions */}
            <div className="flex gap-2">
                <button
                    onClick={handleSend}
                    disabled={isLoading}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                    <Send className="w-4 h-4" />
                    Send Availability
                </button>
                <button
                    onClick={handleCreateEvent}
                    disabled={isLoading || !suggested_slots?.length}
                    className="flex items-center justify-center gap-1.5 bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                    <Calendar className="w-4 h-4" />
                    Create Event
                </button>
                <button
                    onClick={() => onDismiss?.(suggestion.id)}
                    disabled={isLoading}
                    className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Dismiss"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
};

export default SchedulingSuggestionCard;
