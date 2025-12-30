import React, { useMemo, useState } from 'react';
import { CheckCircle2, AlertTriangle, CheckSquare, Clock, Sparkles, ChevronDown, ChevronRight } from 'lucide-react';
import InlineTaskItem from '../components/InlineTaskItem';

/**
 * TaskHub - Dedicated Tasks Screen (Focus Mode)
 *
 * Filter Model:
 * - Default view: Pending approval + Approved (not done)
 * - Filters: Pending approval, Active (approved + in_progress), Completed
 * - Completed section is collapsed by default
 *
 * "What do I need to act on right now?"
 */

const FilterChip = ({ active, onClick, label, count, color = 'blue' }) => {
    const colorClasses = {
        blue: active ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-white text-gray-600 border-gray-200',
        amber: active ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-white text-gray-600 border-gray-200',
        green: active ? 'bg-green-50 text-green-700 border-green-200' : 'bg-white text-gray-600 border-gray-200',
        red: active ? 'bg-red-50 text-red-700 border-red-200' : 'bg-white text-gray-600 border-gray-200',
        purple: active ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-white text-gray-600 border-gray-200',
    };

    return (
        <button
            onClick={onClick}
            className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${colorClasses[color]} hover:opacity-80`}
        >
            {label}
            {count !== undefined && <span className="ml-1.5 opacity-60">({count})</span>}
        </button>
    );
};

const TaskHub = ({ messages, onNavigate, onToggleTask, onApproveTask, onDismissTask }) => {
    const [activeFilter, setActiveFilter] = useState('active'); // 'all', 'pending', 'active', 'waiting'
    const [showCompleted, setShowCompleted] = useState(false);

    // Flatten all tasks from messages
    const allTasks = useMemo(() => {
        return messages.flatMap(m => m.tasks || []);
    }, [messages]);

    // Task categories based on status
    const pendingApprovalTasks = allTasks.filter(t => t.status === 'pending_approval');
    const activeTasks = allTasks.filter(t =>
        (t.status === 'approved' || t.status === 'in_progress') && t.type !== 'waiting_for'
    );
    const waitingTasks = allTasks.filter(t => t.type === 'waiting_for' && t.status !== 'completed' && t.status !== 'dismissed');

    // Only show completed tasks from the last 24 hours
    const now = new Date();
    const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const completedTasks = allTasks.filter(t => {
        if (t.status !== 'completed') return false;
        // Check completed_at timestamp if available
        if (t.completed_at) {
            const completedAt = new Date(t.completed_at);
            return completedAt >= twentyFourHoursAgo;
        }
        // If no completed_at, check updated_at as fallback
        if (t.updated_at) {
            const updatedAt = new Date(t.updated_at);
            return updatedAt >= twentyFourHoursAgo;
        }
        // If no timestamps, show it (assume recently completed in this session)
        return true;
    });

    // Urgent tasks (within active)
    const urgentTasks = activeTasks.filter(t => t.priority === 'urgent');
    const upcomingTasks = activeTasks.filter(t => t.priority !== 'urgent');

    // Filter tasks based on active filter
    const getFilteredTasks = () => {
        switch (activeFilter) {
            case 'pending':
                return { pending: pendingApprovalTasks, active: [], waiting: [] };
            case 'active':
                return { pending: [], active: activeTasks, waiting: [] };
            case 'waiting':
                return { pending: [], active: [], waiting: waitingTasks };
            case 'all':
            default:
                return { pending: pendingApprovalTasks, active: activeTasks, waiting: waitingTasks };
        }
    };

    const filtered = getFilteredTasks();
    const totalActionable = pendingApprovalTasks.length + activeTasks.length + waitingTasks.length;

    return (
        <div className="min-h-screen bg-gray-50 pb-24">
            <div className="bg-white border-b border-gray-200 sticky top-0 z-10 px-4 py-3 shadow-sm">
                <h1 className="text-lg font-bold text-gray-800">Focus Mode</h1>
            </div>

            {/* Filter Chips */}
            <div className="px-4 py-4 flex gap-2 overflow-x-auto no-scrollbar">
                <FilterChip
                    active={activeFilter === 'all'}
                    onClick={() => setActiveFilter('all')}
                    label="All"
                    count={totalActionable}
                    color="blue"
                />
                <FilterChip
                    active={activeFilter === 'pending'}
                    onClick={() => setActiveFilter('pending')}
                    label="Suggested"
                    count={pendingApprovalTasks.length}
                    color="amber"
                />
                <FilterChip
                    active={activeFilter === 'active'}
                    onClick={() => setActiveFilter('active')}
                    label="Active"
                    count={activeTasks.length}
                    color="blue"
                />
                <FilterChip
                    active={activeFilter === 'waiting'}
                    onClick={() => setActiveFilter('waiting')}
                    label="Waiting"
                    count={waitingTasks.length}
                    color="purple"
                />
            </div>

            {/* Stats Summary */}
            <div className="px-4 pb-4 flex gap-2 overflow-x-auto no-scrollbar">
                <div className="bg-red-50 text-red-700 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1 border border-red-100">
                    <AlertTriangle className="w-3 h-3" /> Urgent ({urgentTasks.length})
                </div>
                <div className="bg-amber-50 text-amber-700 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1 border border-amber-100">
                    <Sparkles className="w-3 h-3" /> Pending ({pendingApprovalTasks.length})
                </div>
                <div className="bg-green-50 text-green-700 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1 border border-green-100">
                    <CheckCircle2 className="w-3 h-3" /> Done today ({completedTasks.length})
                </div>
            </div>

            <div className="px-4 space-y-6">
                {/* PENDING APPROVAL - Suggested by AI */}
                {filtered.pending.length > 0 && (
                    <section>
                        <h2 className="text-xs font-bold text-amber-600 uppercase tracking-wider mb-3 flex items-center gap-2">
                            <Sparkles className="w-3 h-3" /> Suggested by AI
                        </h2>
                        <div className="space-y-3">
                            {filtered.pending.map(task => (
                                <InlineTaskItem
                                    key={task.id}
                                    task={task}
                                    onToggle={onToggleTask}
                                    onApprove={onApproveTask}
                                    onDismiss={onDismissTask}
                                />
                            ))}
                        </div>
                    </section>
                )}

                {/* ACTIVE - Approved tasks */}
                {filtered.active.length > 0 && (
                    <>
                        {/* DO NOW - Urgent */}
                        {urgentTasks.length > 0 && (activeFilter === 'all' || activeFilter === 'active') && (
                            <section>
                                <h2 className="text-xs font-bold text-red-600 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <AlertTriangle className="w-3 h-3" /> Do Now
                                </h2>
                                <div className="space-y-3">
                                    {urgentTasks.map(task => (
                                        <InlineTaskItem
                                            key={task.id}
                                            task={task}
                                            onToggle={onToggleTask}
                                            onApprove={onApproveTask}
                                            onDismiss={onDismissTask}
                                        />
                                    ))}
                                </div>
                            </section>
                        )}

                        {/* UPCOMING - Non-urgent */}
                        {upcomingTasks.length > 0 && (activeFilter === 'all' || activeFilter === 'active') && (
                            <section>
                                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <CheckSquare className="w-3 h-3" /> Upcoming
                                </h2>
                                <div className="space-y-3">
                                    {upcomingTasks.map(task => (
                                        <InlineTaskItem
                                            key={task.id}
                                            task={task}
                                            onToggle={onToggleTask}
                                            onApprove={onApproveTask}
                                            onDismiss={onDismissTask}
                                        />
                                    ))}
                                </div>
                            </section>
                        )}
                    </>
                )}

                {/* WAITING FOR */}
                {filtered.waiting.length > 0 && (
                    <section>
                        <h2 className="text-xs font-bold text-purple-600 uppercase tracking-wider mb-3 flex items-center gap-2">
                            <Clock className="w-3 h-3" /> Waiting For
                        </h2>
                        <div className="space-y-3">
                            {filtered.waiting.map(task => (
                                <InlineTaskItem
                                    key={task.id}
                                    task={task}
                                    onToggle={onToggleTask}
                                    onApprove={onApproveTask}
                                    onDismiss={onDismissTask}
                                />
                            ))}
                        </div>
                    </section>
                )}

                {/* Empty State */}
                {totalActionable === 0 && (
                    <div className="text-center py-12 text-gray-400">
                        <CheckCircle2 className="w-12 h-12 mx-auto mb-3 opacity-20" />
                        <p>All caught up! Nice work.</p>
                    </div>
                )}

                {/* COMPLETED - Collapsible History (last 24 hours) */}
                {completedTasks.length > 0 && (
                    <section className="border-t border-gray-200 pt-6">
                        <button
                            onClick={() => setShowCompleted(!showCompleted)}
                            className="w-full flex items-center justify-between text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 hover:text-gray-600 transition-colors"
                        >
                            <span className="flex items-center gap-2">
                                <CheckCircle2 className="w-3 h-3" /> Completed - Last 24h ({completedTasks.length})
                            </span>
                            {showCompleted ? (
                                <ChevronDown className="w-4 h-4" />
                            ) : (
                                <ChevronRight className="w-4 h-4" />
                            )}
                        </button>
                        {showCompleted && (
                            <div className="space-y-3">
                                {completedTasks.map(task => (
                                    <InlineTaskItem
                                        key={task.id}
                                        task={task}
                                        onToggle={onToggleTask}
                                        showInHistory={true}
                                    />
                                ))}
                            </div>
                        )}
                    </section>
                )}
            </div>
        </div>
    );
};

export default TaskHub;
