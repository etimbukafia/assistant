import React, { useState } from 'react';
import { Clock, Calendar, CheckCircle2, Info, ArrowRight, Sparkles, Check, X, Play } from 'lucide-react';

/**
 * Task Status Model:
 * - pending_approval: "Suggested by AI" - needs user approval before becoming actionable
 * - approved: Normal task - can be checked off
 * - in_progress: Task being worked on
 * - completed: Done (hidden inline, visible in history)
 * - dismissed: Hidden everywhere
 *
 * Golden Rule: If it can be checked off, it must be a real task in the DB.
 */

const InlineTaskItem = ({ task, onToggle, onApprove, onDismiss, showInHistory = false }) => {
    const [showSource, setShowSource] = useState(false);
    const [isCompleted, setIsCompleted] = useState(task.status === 'completed');
    const [isAnimating, setIsAnimating] = useState(false);

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
                                {task.follow_up_condition === 'no_reply' ? 'Follow up if no reply' : `Due: ${task.deadline}`}
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
        return (
            <div className="mt-2 bg-amber-50 border border-amber-200 border-dashed rounded-lg p-3">
                <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                        <Sparkles className="w-4 h-4 text-amber-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-amber-600 uppercase tracking-wide">
                                Suggested by AI
                            </span>
                            {task.confidence && (
                                <span className="text-xs text-amber-400">
                                    {Math.round(task.confidence * 100)}% confident
                                </span>
                            )}
                        </div>
                        <p className="text-sm font-medium text-gray-800">{task.title}</p>
                        {task.deadline && (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-600 mt-1">
                                <Calendar className="w-3 h-3" />
                                {task.deadline}
                            </span>
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

    return (
        <div className={`mt-2 transition-all duration-300 ${displayCompleted && !showInHistory ? 'opacity-50' : 'opacity-100'} ${isAnimating ? 'scale-95' : 'scale-100'}`}>
            <div className={`border rounded-lg p-3 bg-white flex items-start gap-3 shadow-sm ${displayCompleted ? 'bg-gray-50' : ''}`}>
                {/* Checkbox for approved/in_progress tasks */}
                <div
                    onClick={handleToggle}
                    className={`mt-0.5 w-5 h-5 rounded border-2 cursor-pointer flex items-center justify-center transition-all ${
                        displayCompleted
                            ? 'bg-green-500 border-green-500'
                            : isInProgress
                                ? 'bg-blue-500 border-blue-500'
                                : 'border-gray-300 hover:border-blue-500'
                    }`}
                >
                    {displayCompleted && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                    {isInProgress && !displayCompleted && <Play className="w-3 h-3 text-white" />}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium text-gray-800 ${displayCompleted ? 'line-through text-gray-400' : ''}`}>
                            {task.title}
                        </span>
                        {isInProgress && !displayCompleted && (
                            <span className="text-xs font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                                In Progress
                            </span>
                        )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 mt-1.5">
                        {task.deadline && (
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${priorityColor} flex items-center gap-1`}>
                                <Calendar className="w-3 h-3" />
                                {task.deadline}
                            </span>
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
            </div>
        </div>
    );
};

export default InlineTaskItem;
