import React, { useState } from 'react';
import { RefreshCw, Sparkles, CheckCircle2, Archive, Check, Trash2, RotateCcw } from 'lucide-react';
import InlineTaskItem from '../components/InlineTaskItem';
import ExtractedTaskSuggestion from '../components/ExtractedTaskSuggestion';
import PatternSuggestionBanner from '../components/PatternSuggestionBanner';
import { timeAgo } from '../utils/helpers';
import { API_BASE_URL } from '../utils/constants';

const FilterButton = ({ active, onClick, label, count, urgent }) => (
    <button
        onClick={onClick}
        className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors border ${active
            ? urgent
                ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-blue-50 border-blue-200 text-blue-700'
            : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
    >
        {label}
        {count !== undefined && <span className="ml-1.5 opacity-60">({count})</span>}
    </button>
);

/**
 * Task Status Filtering (Inline on Message Card):
 * Show only: pending_approval, approved (not completed)
 * Hide: completed, dismissed
 *
 * Extracted tasks (raw AI extraction):
 * Show only if no structured tasks exist OR behind "Detected by AI" label
 */
const MessageCard = ({ message, onClick, onToggleTask, onApproveTask, onDismissTask, onApproveExtractedTask, onMarkDone, onArchive, onDelete, isArchiveView }) => {
    // Filter tasks for inline display: only pending_approval and approved (not completed/dismissed)
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
        <div
            onClick={onClick}
            className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm active:scale-[0.99] transition-transform cursor-pointer"
        >
            {/* Header */}
            <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                    {message.needs_reply && (
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
                    )}
                    <span className={`font-semibold ${message.needs_reply ? 'text-gray-900' : 'text-gray-600'}`}>
                        {message.sender.split('@')[0]}
                    </span>
                    <span className="text-xs text-gray-400">• {timeAgo(message.received_at)}</span>
                </div>
            </div>

            <h3 className="font-medium text-gray-800 mb-1">{message.subject}</h3>

            {/* AI Summary */}
            <div className="text-sm text-gray-600 leading-relaxed mb-4 p-3 bg-blue-50/50 rounded-lg border border-blue-100/50">
                <div className="flex items-center gap-1 text-blue-800 text-xs font-semibold mb-1">
                    <Sparkles className="w-3 h-3" /> ASSISTANT SUMMARY
                </div>
                {message.summary}
            </div>

            {/* Task Intelligence Layer - Primary Tasks */}
            {inlineTasks.length > 0 && (
                <div className="mb-4">
                    <div className="flex items-center gap-2 text-xs font-bold text-gray-400 mb-2 uppercase tracking-wider">
                        <CheckCircle2 className="w-3 h-3" /> Actions & Intelligence
                    </div>
                    <div className="space-y-1">
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
                <div className="mb-4">
                    <div className="flex items-center gap-2 text-xs font-bold text-gray-400 mb-2 uppercase tracking-wider">
                        <Sparkles className="w-3 h-3" /> AI Detected
                    </div>
                    <div className="space-y-1">
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

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t border-gray-50">
                {isArchiveView ? (
                    <>
                        <button
                            className="flex-1 bg-blue-50 text-blue-700 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1"
                            onClick={(e) => { e.stopPropagation(); onMarkDone?.(message.id, true); }}
                            title="Move back to inbox"
                        >
                            <RotateCcw className="w-4 h-4" />
                            Restore
                        </button>
                        <button
                            className="px-3 bg-red-50 text-red-600 py-2 rounded-lg text-sm font-medium hover:bg-red-100"
                            onClick={(e) => { e.stopPropagation(); onDelete?.(message.id); }}
                            title="Delete permanently"
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                    </>
                ) : (
                    <>
                        {message.needs_reply ? (
                            <button
                                className="flex-1 bg-blue-50 text-blue-700 py-2 rounded-lg text-sm font-medium"
                                onClick={(e) => { e.stopPropagation(); onClick(); }}
                            >
                                Reply
                            </button>
                        ) : (
                            <button
                                className="flex-1 bg-green-50 text-green-700 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1"
                                onClick={(e) => { e.stopPropagation(); onMarkDone?.(message.id); }}
                            >
                                <Check className="w-4 h-4" />
                                Done
                            </button>
                        )}
                        <button
                            className="px-3 bg-gray-50 text-gray-500 py-2 rounded-lg text-sm font-medium hover:bg-gray-100"
                            onClick={(e) => { e.stopPropagation(); onArchive?.(message.id); }}
                            title="Archive"
                        >
                            <Archive className="w-4 h-4" />
                        </button>
                        <button
                            className="px-3 bg-gray-50 text-red-400 py-2 rounded-lg text-sm font-medium hover:bg-red-50"
                            onClick={(e) => { e.stopPropagation(); onDelete?.(message.id); }}
                            title="Delete"
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

const Dashboard = ({
    messages,
    stats,
    onNavigate,
    onSync,
    isSyncing,
    filter,
    setFilter,
    demoMode,
    onToggleTask,
    onApproveTask,
    onDismissTask,
    onApproveExtractedTask,
    onMarkDone,
    onArchive,
    onDelete,
    isArchiveView = false
}) => {
    const [showDebug, setShowDebug] = useState(false);
    const [debugLog, setDebugLog] = useState('');

    const testAPI = async (endpoint, method = 'GET') => {
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`, { method });
            const data = await res.json();
            setDebugLog(`✅ ${method} ${endpoint}\n${JSON.stringify(data, null, 2)}`);
        } catch (err) {
            setDebugLog(`❌ ${method} ${endpoint}\n${err.message}`);
        }
    };

    // Calculate counts from actual messages (fixes count not updating issue)
    const allCount = messages.length;
    const urgentCount = messages.filter(m => m.needs_reply).length;
    const todayCount = messages.filter(m => {
        const received = new Date(m.received_at);
        const now = new Date();
        return (now.getTime() - received.getTime()) < 24 * 60 * 60 * 1000;
    }).length;

    // Filter logic
    const filteredMessages = messages.filter(m => {
        if (filter === 'urgent') return m.needs_reply;
        if (filter === 'today') {
            const received = new Date(m.received_at);
            const now = new Date();
            return (now.getTime() - received.getTime()) < 24 * 60 * 60 * 1000;
        }
        return true;
    });

    // Sort: Urgent first, then new
    const sortedMessages = [...filteredMessages].sort((a, b) => {
        if (a.needs_reply && !b.needs_reply) return -1;
        if (!a.needs_reply && b.needs_reply) return 1;
        return new Date(b.received_at).getTime() - new Date(a.received_at).getTime();
    });

    return (
        <div className="min-h-screen bg-gray-50 pb-24">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 sticky top-0 z-10 px-4 py-3 flex justify-between items-center shadow-sm">
                <h1 className="text-lg font-bold text-gray-800">{isArchiveView ? 'Archive' : 'Inbox'}</h1>
                <div className="flex gap-2">
                    {!demoMode && !isArchiveView && (
                        <button
                            onClick={() => setShowDebug(!showDebug)}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-purple-50 text-purple-600 hover:bg-purple-100"
                        >
                            API Test
                        </button>
                    )}
                    {!isArchiveView && (
                        <button
                            onClick={onSync}
                            disabled={isSyncing}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${isSyncing
                                ? 'bg-blue-50 text-blue-600'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                }`}
                        >
                            <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
                            {isSyncing ? 'Syncing...' : 'Sync'}
                        </button>
                    )}
                </div>
            </div>

            {/* Debug Panel */}
            {showDebug && (
                <div className="bg-gray-900 text-white p-4 border-b border-gray-700">
                    <div className="max-w-4xl mx-auto">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="font-bold text-sm">API Test Panel</h3>
                            <button
                                onClick={() => setShowDebug(false)}
                                className="text-gray-400 hover:text-white text-xs"
                            >
                                Close
                            </button>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
                            <button onClick={() => testAPI('/auth/gmail/status')} className="bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-xs font-medium">Auth Status</button>
                            <button onClick={() => testAPI('/sync', 'POST')} className="bg-green-600 hover:bg-green-700 px-3 py-2 rounded text-xs font-medium">Sync Messages</button>
                            <button onClick={() => testAPI('/messages')} className="bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded text-xs font-medium">Get Messages</button>
                            <button onClick={() => testAPI('/stats')} className="bg-orange-600 hover:bg-orange-700 px-3 py-2 rounded text-xs font-medium">Get Stats</button>
                            <button onClick={() => testAPI('/tasks')} className="bg-pink-600 hover:bg-pink-700 px-3 py-2 rounded text-xs font-medium">Get Tasks</button>
                            <button onClick={() => testAPI('/settings')} className="bg-indigo-600 hover:bg-indigo-700 px-3 py-2 rounded text-xs font-medium">Get Settings</button>
                        </div>

                        {debugLog && (
                            <div className="bg-black rounded p-3 font-mono text-xs overflow-auto max-h-64">
                                <pre className="whitespace-pre-wrap">{debugLog}</pre>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Filters - only show in inbox view */}
            {!isArchiveView && (
                <div className="px-4 py-3 flex gap-2 overflow-x-auto no-scrollbar">
                    <FilterButton active={filter === 'all'} onClick={() => setFilter('all')} label="All" count={allCount} />
                    <FilterButton active={filter === 'urgent'} onClick={() => setFilter('urgent')} label="Urgent" count={urgentCount} urgent />
                    <FilterButton active={filter === 'today'} onClick={() => setFilter('today')} label="Today" count={todayCount} />
                </div>
            )}

            {/* Pattern Suggestions (Phase 1 - suggest only) - only in inbox */}
            {!isArchiveView && (
                <div className="px-4">
                    <PatternSuggestionBanner demoMode={demoMode} />
                </div>
            )}

            {/* Feed */}
            <div className="px-4 space-y-3">
                {sortedMessages.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                        <p>{isArchiveView ? 'No archived messages.' : 'No messages found.'}</p>
                    </div>
                ) : (
                    sortedMessages.map(msg => (
                        <MessageCard
                            key={msg.id}
                            message={msg}
                            onClick={() => onNavigate('detail', { id: msg.id })}
                            onToggleTask={onToggleTask}
                            onApproveTask={onApproveTask}
                            onDismissTask={onDismissTask}
                            onApproveExtractedTask={onApproveExtractedTask}
                            onMarkDone={onMarkDone}
                            onArchive={onArchive}
                            onDelete={onDelete}
                            isArchiveView={isArchiveView}
                        />
                    ))
                )}
            </div>
        </div>
    );
};

export default Dashboard;
