import React from 'react';
import { ChevronLeft, Sparkles, Calendar, User, MoreVertical, CheckCircle2 } from 'lucide-react';
import InlineTaskItem from '../components/InlineTaskItem';
import ExtractedTaskSuggestion from '../components/ExtractedTaskSuggestion';
import SchedulingSuggestionCard from '../components/SchedulingSuggestionCard';
import { timeAgo } from '../utils/helpers';

/**
 * MessageDetail - Full message view with task hierarchy
 *
 * Task Display Rules:
 * - Primary: message.tasks (structured tasks from DB)
 *   - Show pending_approval, approved, in_progress inline
 *   - Hide completed, dismissed
 * - Secondary: message.extracted_tasks (raw AI extraction)
 *   - Show only if no structured tasks exist
 *   - Read-only with "Approve as task" button
 *
 * Scheduling:
 * - Shows SchedulingSuggestionCard if scheduling intent detected
 */
const MessageDetail = ({
    message,
    onBack,
    onDraftReply,
    onToggleTask,
    onApproveTask,
    onDismissTask,
    onApproveExtractedTask,
    schedulingSuggestion,
    onSendScheduling,
    onDismissScheduling,
    onCreateCalendarEvent,
    onRefreshScheduling,
    isRefreshingScheduling
}) => {
    if (!message) return null;

    // Filter tasks for inline display: only pending_approval, approved, in_progress
    const inlineTasks = (message.tasks || []).filter(task =>
        task.status === 'pending_approval' ||
        task.status === 'approved' ||
        task.status === 'in_progress'
    );

    // Check if we have any structured tasks (regardless of status)
    const hasStructuredTasks = (message.tasks || []).length > 0;

    // Show extracted_tasks only if no structured tasks exist
    const showExtractedTasks = !hasStructuredTasks && (message.extracted_tasks || []).length > 0;

    return (
        <div className="min-h-screen bg-white pb-24">
            {/* Header */}
            <div className="sticky top-0 bg-white/90 backdrop-blur-md border-b border-gray-100 px-4 py-3 flex items-center gap-3 z-10">
                <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full">
                    <ChevronLeft className="w-6 h-6 text-gray-600" />
                </button>
                <div className="flex-1 min-w-0">
                    <h2 className="font-semibold text-gray-900 truncate">{message.subject}</h2>
                </div>
            </div>

            <div className="p-4 space-y-6">
                {/* Meta */}
                <div className="flex justify-between items-start">
                    <div>
                        <div className="font-bold text-lg text-gray-900">{message.sender}</div>
                        <div className="text-sm text-gray-500">To: You</div>
                    </div>
                    <div className="text-sm text-gray-400">{timeAgo(message.received_at)}</div>
                </div>

                {/* AI Summary */}
                <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                    <div className="flex items-center gap-2 mb-2 text-blue-800 font-semibold text-sm">
                        <Sparkles className="w-4 h-4" /> ASSISTANT SUMMARY
                    </div>
                    <p className="text-blue-900 leading-relaxed text-sm">{message.summary}</p>
                </div>

                {/* Scheduling Suggestion */}
                {schedulingSuggestion && (
                    <SchedulingSuggestionCard
                        suggestion={schedulingSuggestion}
                        onSend={onSendScheduling}
                        onDismiss={onDismissScheduling}
                        onCreateEvent={onCreateCalendarEvent}
                        onRefresh={onRefreshScheduling}
                        isRefreshing={isRefreshingScheduling}
                    />
                )}

                {/* Task Intelligence - Primary Tasks */}
                {inlineTasks.length > 0 && (
                    <div className="border border-gray-200 rounded-xl p-4">
                        <h3 className="font-semibold text-gray-900 mb-3 text-sm flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-gray-500" />
                            Tasks & Intelligence
                        </h3>
                        <div className="space-y-2">
                            {inlineTasks.map(task => (
                                <InlineTaskItem
                                    key={task.id}
                                    task={task}
                                    onToggle={onToggleTask}
                                    onApprove={onApproveTask}
                                    onDismiss={onDismissTask}
                                />
                            ))}
                        </div>
                    </div>
                )}

                {/* Extracted Tasks - Secondary (only if no structured tasks) */}
                {showExtractedTasks && (
                    <div className="border border-gray-200 border-dashed rounded-xl p-4">
                        <h3 className="font-semibold text-gray-700 mb-3 text-sm flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-amber-500" />
                            AI Detected Items
                        </h3>
                        <p className="text-xs text-gray-500 mb-3">
                            These potential tasks were detected by AI. Approve to convert to actionable tasks.
                        </p>
                        <div className="space-y-2">
                            {message.extracted_tasks.map((text, idx) => (
                                <ExtractedTaskSuggestion
                                    key={`${message.id}-extracted-${idx}`}
                                    text={text}
                                    messageId={message.id}
                                    onApprove={onApproveExtractedTask}
                                />
                            ))}
                        </div>
                    </div>
                )}

                {/* Extracted Data */}
                <div className="grid gap-4">
                    {message.extracted_dates && message.extracted_dates.length > 0 && (
                        <div className="border border-gray-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3 text-gray-700 font-semibold text-sm">
                                <Calendar className="w-4 h-4 text-orange-500" /> DATES
                            </div>
                            <ul className="space-y-2">
                                {message.extracted_dates.map((date, i) => (
                                    <li key={i} className="text-gray-800 text-sm bg-orange-50 inline-block px-2 py-1 rounded-md">
                                        {date}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {message.extracted_people && message.extracted_people.length > 0 && (
                        <div className="border border-gray-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3 text-gray-700 font-semibold text-sm">
                                <User className="w-4 h-4 text-purple-500" /> PEOPLE
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {message.extracted_people.map((person, i) => (
                                    <span key={i} className="text-gray-800 text-sm bg-purple-50 px-2 py-1 rounded-md">
                                        {person}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Full Email */}
                <details className="group border border-gray-200 rounded-xl overflow-hidden">
                    <summary className="flex items-center justify-between p-4 bg-gray-50 cursor-pointer list-none font-medium text-gray-700 group-open:border-b border-gray-200">
                        <span>Show Full Email</span>
                        <MoreVertical className="w-4 h-4 text-gray-400 group-open:rotate-90 transition-transform" />
                    </summary>
                    <div className="p-4 bg-white text-sm text-gray-600 whitespace-pre-wrap leading-relaxed">
                        {message.body || "No body content available."}
                    </div>
                </details>
            </div>

            {/* Floating Action */}
            {message.needs_reply && (
                <div className="fixed bottom-24 left-4 right-4 max-w-md mx-auto z-40">
                    <button
                        onClick={() => onDraftReply(message.id)}
                        className="w-full bg-blue-600 text-white font-semibold py-4 rounded-xl shadow-lg flex items-center justify-center gap-2"
                    >
                        <Sparkles className="w-5 h-5" /> Generate Reply
                    </button>
                </div>
            )}
        </div>
    );
};

export default MessageDetail;
