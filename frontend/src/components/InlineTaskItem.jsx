import React, { useState } from 'react';
import { Clock, Calendar, CheckCircle2, Info, ArrowRight, Sparkles, Check, X, Play, AlertTriangle, Edit2, Save } from 'lucide-react';
import { isUrgentTask } from '../utils/urgency';

/**
 * Task Status Model:
 * - pending_approval: "Suggested by AI" - needs user approval before becoming actionable
 * - approved: Normal task - can be checked off
 * - in_progress: Task being worked on
 * - completed: Done (hidden inline, visible in history)
 * - dismissed: Hidden everywhere
 *
 * Deadline Fields (Smart Todo List):
 * - deadline: ISO datetime string or formatted string
 * - deadline_source: "explicit" | "inferred"
 * - deadline_confidence: 0.0-1.0 for inferred deadlines
 * - deadline_user_confirmed: boolean
 * - urgency_suggested_by_ai: boolean (priority=urgent AND suggested by AI)
 *
 * Golden Rule: If it can be checked off, it must be a real task in the DB.
 */

// Helper to format deadline for display
const formatDeadline = (deadline) => {
    if (!deadline) return null;
    // If it's already a formatted string (from mock), return as-is
    if (typeof deadline === 'string' && !deadline.includes('T')) {
        return deadline;
    }
    try {
        const date = new Date(deadline);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();
        const tomorrow = new Date(now);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const isTomorrow = date.toDateString() === tomorrow.toDateString();

        // Check if time is meaningful (not midnight)
        const hasTime = date.getHours() !== 0 || date.getMinutes() !== 0;
        const timeStr = hasTime ? ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

        if (isToday) return 'Today' + timeStr;
        if (isTomorrow) return 'Tomorrow' + timeStr;
        return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) + timeStr;
    } catch {
        return deadline;
    }
};

// Check if deadline is overdue
const isOverdue = (deadline) => {
    if (!deadline) return false;
    try {
        return new Date(deadline) < new Date();
    } catch {
        return false;
    }
};

const InlineTaskItem = ({
    task,
    onToggle,
    onApprove,
    onDismiss,
    onUpdate,
    onConfirmDeadline,
    onConfirmUrgency,
    showInHistory = false,
    inboxView = false  // When true, approved tasks are greyed out and not interactive
}) => {
    const [showSource, setShowSource] = useState(false);
    const [isCompleted, setIsCompleted] = useState(task.status === 'completed');
    const [isAnimating, setIsAnimating] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(task.title);
    const [editPriority, setEditPriority] = useState(task.priority);
    const [editDeadline, setEditDeadline] = useState(task.deadline ? new Date(task.deadline).toISOString().slice(0, 16) : '');

    // Check if this task is urgent (Phase 3 - visual highlighting)
    const taskIsUrgent = isUrgentTask(task);

    const handleToggle = (e) => {
        e.stopPropagation();
        // Only approved and in_progress tasks can be toggled
        if (task.status !== 'approved' && task.status !== 'in_progress') return;

        setIsAnimating(true);
        setIsCompleted(!isCompleted);
        setTimeout(() => {
            onToggle(task.id);
            setIsAnimating(false);
        }, 300);
    };

    const handleApprove = (e) => {
        e.stopPropagation();
        if (onApprove) {
            onApprove(task.id);
        }
    };

    const handleDismiss = (e) => {
        e.stopPropagation();
        if (onDismiss) {
            onDismiss(task.id);
        }
    };

    const handleConfirmDeadline = (e) => {
        e.stopPropagation();
        if (onConfirmDeadline) {
            onConfirmDeadline(task.id);
        }
    };

    const handleConfirmUrgency = (e) => {
        e.stopPropagation();
        if (onConfirmUrgency) {
            onConfirmUrgency(task.id);
        }
    };

    const handleSaveEdit = (e) => {
        e.stopPropagation();
        if (onUpdate) {
            const updates = {};
            if (editTitle !== task.title) updates.title = editTitle;
            if (editPriority !== task.priority) updates.priority = editPriority;
            if (editDeadline) {
                updates.deadline = new Date(editDeadline).toISOString();
            }
            if (Object.keys(updates).length > 0) {
                onUpdate(task.id, updates);
            }
        }
        setIsEditing(false);
    };

    // Waiting For type (blocking tasks)
    if (task.type === 'waiting_for') {
        return (
            <div className="mt-2 bg-purple-50 border border-purple-100 rounded-lg p-3">
                <div className="flex items-start gap-3">
                    <Clock className="w-5 h-5 text-purple-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-purple-900">Waiting for: {task.title}</div>
                        {task.follow_up_condition && (
                            <div className="text-xs text-purple-600 mt-1 flex items-center gap-1">
                                <ArrowRight className="w-3 h-3" />
                                {task.follow_up_condition === 'no_reply' ? 'Follow up if no reply' : `Due: ${formatDeadline(task.deadline)}`}
                            </div>
                        )}
                        {task.source_snippet && (
                            <button
                                onClick={(e) => { e.stopPropagation(); setShowSource(!showSource); }}
                                className="text-xs text-purple-400 hover:text-purple-600 mt-2 flex items-center gap-1"
                            >
                                <Info className="w-3 h-3" /> Why?
                            </button>
                        )}
                        {showSource && task.source_snippet && (
                            <div className="mt-2 text-xs italic text-purple-700 bg-purple-100/50 p-2 rounded">
                                "{task.source_snippet}"
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // Pending Approval - "Suggested by AI" style
    if (task.status === 'pending_approval') {
        const deadlineDisplay = formatDeadline(task.deadline);
        const isSuggestedDeadline = task.deadline && task.deadline_source === 'inferred' && !task.deadline_user_confirmed;
        const isSuggestedUrgent = task.priority === 'urgent' && task.urgency_suggested_by_ai;

        return (
            <div className="mt-2 bg-amber-50 border border-amber-200 border-dashed rounded-lg p-3">
                <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                        <Sparkles className="w-4 h-4 text-amber-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-xs font-medium text-amber-600 uppercase tracking-wide">
                                Suggested by AI
                            </span>
                            {task.confidence && (
                                <span className="text-xs text-amber-400">
                                    {Math.round(task.confidence * 100)}% confident
                                </span>
                            )}
                            {isSuggestedUrgent && (
                                <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 bg-amber-100 px-2 py-0.5 rounded-full">
                                    <AlertTriangle className="w-3 h-3" />
                                    Suggested Urgent
                                    <button
                                        onClick={handleConfirmUrgency}
                                        className="ml-1 text-green-600 hover:text-green-700"
                                        title="Confirm urgency"
                                    >
                                        <Check className="w-3 h-3" />
                                    </button>
                                </span>
                            )}
                        </div>
                        <p className="text-sm font-medium text-gray-800">{task.title}</p>
                        {deadlineDisplay && (
                            <div className="flex items-center gap-2 mt-1">
                                <span
                                    className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${isSuggestedDeadline
                                        ? 'text-amber-600 bg-amber-100 border border-amber-200'
                                        : 'text-blue-600 bg-blue-50 border border-blue-100'
                                        }`}
                                    title={isSuggestedDeadline ? `AI detected deadline from: "${task.deadline_original_text || 'context'}"` : undefined}
                                >
                                    <Calendar className="w-3 h-3" />
                                    {deadlineDisplay}
                                    {isSuggestedDeadline && ' (AI suggested)'}
                                </span>
                                {isSuggestedDeadline && task.deadline_confidence && (
                                    <span className="text-xs text-gray-400">
                                        {Math.round(task.deadline_confidence * 100)}%
                                    </span>
                                )}
                                {isSuggestedDeadline && (
                                    <button
                                        onClick={handleConfirmDeadline}
                                        className="text-xs text-green-600 hover:text-green-700 flex items-center gap-0.5"
                                        title="Confirm deadline"
                                    >
                                        <Check className="w-3 h-3" /> Confirm
                                    </button>
                                )}
                            </div>
                        )}
                        {task.source_snippet && (
                            <>
                                <button
                                    onClick={(e) => { e.stopPropagation(); setShowSource(!showSource); }}
                                    className="text-xs text-amber-400 hover:text-amber-600 mt-2 flex items-center gap-1"
                                >
                                    <Info className="w-3 h-3" /> Why?
                                </button>
                                {showSource && (
                                    <div className="mt-2 text-xs italic text-amber-700 bg-amber-100/50 p-2 rounded">
                                        "{task.source_snippet}"
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                    <div className="flex-shrink-0 flex gap-1">
                        <button
                            onClick={handleApprove}
                            className="p-1.5 text-green-600 bg-green-50 rounded-md hover:bg-green-100 transition-colors"
                            title="Approve task"
                        >
                            <Check className="w-4 h-4" />
                        </button>
                        <button
                            onClick={handleDismiss}
                            className="p-1.5 text-gray-400 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                            title="Dismiss"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Standard Actionable Task (approved, in_progress, completed)
    const priorityColor =
        task.priority === 'urgent' ? 'text-red-600 bg-red-50 border-red-100' :
            task.priority === 'high' ? 'text-orange-600 bg-orange-50 border-orange-100' :
                'text-blue-600 bg-blue-50 border-blue-100';

    const isInProgress = task.status === 'in_progress';
    const displayCompleted = isCompleted || task.status === 'completed';
    const deadlineDisplay = formatDeadline(task.deadline);
    const isTaskOverdue = isOverdue(task.deadline) && !displayCompleted;
    const isSuggestedDeadline = task.deadline && task.deadline_source === 'inferred' && !task.deadline_user_confirmed;
    const isSuggestedUrgent = task.priority === 'urgent' && task.urgency_suggested_by_ai;

    // In inbox view, approved tasks are greyed out (manage in Tasks page)
    const isGreyedInInbox = inboxView && task.status === 'approved';

    // Edit mode
    if (isEditing) {
        return (
            <div className="mt-2 border rounded-lg p-3 bg-white shadow-sm">
                <div className="space-y-3">
                    <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="w-full text-sm font-medium text-gray-800 border border-gray-200 rounded px-2 py-1 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="Task title"
                    />
                    <div className="flex gap-2">
                        <select
                            value={editPriority}
                            onChange={(e) => setEditPriority(e.target.value)}
                            className="text-xs border border-gray-200 rounded px-2 py-1"
                        >
                            <option value="low">Low</option>
                            <option value="normal">Normal</option>
                            <option value="high">High</option>
                            <option value="urgent">Urgent</option>
                        </select>
                        <input
                            type="datetime-local"
                            value={editDeadline}
                            onChange={(e) => setEditDeadline(e.target.value)}
                            className="text-xs border border-gray-200 rounded px-2 py-1 flex-1"
                        />
                    </div>
                    <div className="flex justify-end gap-2">
                        <button
                            onClick={() => setIsEditing(false)}
                            className="px-3 py-1 text-xs text-gray-600 bg-gray-100 rounded hover:bg-gray-200"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSaveEdit}
                            className="px-3 py-1 text-xs text-white bg-blue-500 rounded hover:bg-blue-600 flex items-center gap-1"
                        >
                            <Save className="w-3 h-3" /> Save
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={`mt-2 transition-all duration-300 ${(displayCompleted && !showInHistory) || isGreyedInInbox ? 'opacity-60' : 'opacity-100'} ${isAnimating ? 'scale-95' : 'scale-100'}`}>
            <div className={`border rounded-lg p-3 bg-white flex items-start gap-3 shadow-sm 
                ${displayCompleted || isGreyedInInbox ? 'bg-gray-50' : ''} 
                ${taskIsUrgent && !displayCompleted && !isGreyedInInbox ? 'border-l-4 border-l-red-500 bg-red-50/30' : ''}`}>
                {/* Checkbox for approved/in_progress tasks - greyed if approved in inbox */}
                {isGreyedInInbox ? (
                    <div className="mt-0.5 w-5 h-5 rounded bg-amber-100 border-2 border-amber-300 flex items-center justify-center">
                        <Check className="w-3 h-3 text-amber-600" />
                    </div>
                ) : (
                    <div
                        onClick={handleToggle}
                        className={`mt-0.5 w-5 h-5 rounded border-2 cursor-pointer flex items-center justify-center transition-all ${displayCompleted
                            ? 'bg-green-500 border-green-500'
                            : isInProgress
                                ? 'bg-blue-500 border-blue-500'
                                : 'border-gray-300 hover:border-blue-500'
                            }`}
                    >
                        {displayCompleted && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                        {isInProgress && !displayCompleted && <Play className="w-3 h-3 text-white" />}
                    </div>
                )}

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-sm font-medium ${isGreyedInInbox ? 'text-gray-500' : displayCompleted ? 'line-through text-gray-400' : 'text-gray-800'}`}>
                            {task.title}
                        </span>
                        {isGreyedInInbox && (
                            <span className="text-xs font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
                                Added to Tasks
                            </span>
                        )}
                        {isInProgress && !displayCompleted && !isGreyedInInbox && (
                            <span className="text-xs font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                                In Progress
                            </span>
                        )}
                        {isSuggestedUrgent && !displayCompleted && (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
                                <AlertTriangle className="w-3 h-3" />
                                Suggested Urgent
                                <button
                                    onClick={handleConfirmUrgency}
                                    className="ml-0.5 text-green-600 hover:text-green-700"
                                    title="Confirm urgency"
                                >
                                    <Check className="w-3 h-3" />
                                </button>
                            </span>
                        )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 mt-1.5">
                        {deadlineDisplay && (
                            <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 ${isTaskOverdue
                                ? 'text-red-600 bg-red-50 border-red-200'
                                : isSuggestedDeadline
                                    ? 'text-amber-600 bg-amber-50 border-amber-200'
                                    : priorityColor
                                }`}>
                                <Calendar className="w-3 h-3" />
                                {deadlineDisplay}
                                {isSuggestedDeadline && ' (suggested)'}
                                {isTaskOverdue && ' - Overdue'}
                            </span>
                        )}
                        {isSuggestedDeadline && !displayCompleted && (
                            <button
                                onClick={handleConfirmDeadline}
                                className="text-xs text-green-600 hover:text-green-700 flex items-center gap-0.5"
                                title="Confirm deadline"
                            >
                                <Check className="w-3 h-3" /> Confirm
                            </button>
                        )}
                        {task.source_snippet && (
                            <button
                                onClick={(e) => { e.stopPropagation(); setShowSource(!showSource); }}
                                className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
                            >
                                <Info className="w-3 h-3" /> Why?
                            </button>
                        )}
                    </div>

                    {showSource && task.source_snippet && (
                        <div className="mt-2 text-xs italic text-gray-500 bg-gray-50 p-2 rounded border border-gray-100">
                            Source: "{task.source_snippet}"
                        </div>
                    )}
                </div>

                {/* Edit button for approved tasks */}
                {task.status === 'approved' && !displayCompleted && onUpdate && (
                    <button
                        onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
                        className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                        title="Edit task"
                    >
                        <Edit2 className="w-4 h-4" />
                    </button>
                )}
            </div>
        </div>
    );
};

export default InlineTaskItem;
