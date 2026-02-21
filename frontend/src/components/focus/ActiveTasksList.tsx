"use client";

import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getTasksInfinite } from "@/services/tasks";
import { TaskItem } from "@/components/focus/TaskItem";
import { useTaskMutations, useTaskStats } from "@/hooks/useTasks";
import type { Task } from "@/services/messages";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Plus } from "lucide-react";

const PAGE_SIZE = 5;
const CARD_SHADOW = '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)';

type TaskTab = "inbox" | "active" | "waiting" | "done";
type SortMode = "default" | "priority" | "deadline";

const TAB_LABELS: Record<TaskTab, string> = {
    inbox: "Pending",
    active: "Active",
    waiting: "Waiting",
    done: "Done",
};

const SORT_LABELS: Record<SortMode, string> = {
    default: "Default",
    priority: "Priority",
    deadline: "Deadline",
};

const FILTER_BY_TAB: Record<TaskTab, { status?: string[]; priority?: string[] }> = {
    inbox: { status: ["pending_approval"] },
    active: { status: ["approved", "in_progress"] },
    waiting: { status: ["waiting_for"] },
    done: { status: ["completed"] },
};

const toLocalInputValue = (iso: string) => {
    const date = new Date(iso);
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

// ── Styling ────────────────────────────────────────────────────────────────
const tabBase = "rounded-full border px-4 py-1.5 text-[13px] font-medium transition-all font-inter";
const sortBase = "rounded-full border px-3 py-1 text-[12px] font-medium transition-all font-inter";
const utilBtn = "rounded-full border border-border px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition hover:text-foreground font-inter";

const tabClasses: Record<TaskTab, { active: string; idle: string }> = {
    inbox: {
        active: "border-copper bg-copper text-white",
        idle: "border-copper/30 text-copper/80 hover:border-copper/60 hover:text-copper",
    },
    active: {
        active: "border-sage bg-sage text-white",
        idle: "border-sage/30 text-sage/80 hover:border-sage/60 hover:text-sage",
    },
    waiting: {
        active: "border-teal bg-teal text-white",
        idle: "border-teal/30 text-teal/80 hover:border-teal/60 hover:text-teal",
    },
    done: {
        active: "border-obsidian bg-obsidian text-white",
        idle: "border-obsidian/30 text-obsidian/60 hover:border-obsidian/60 hover:text-obsidian",
    },
};

export const ActiveTasksList = () => {
    const [activeTab, setActiveTab] = useState<TaskTab>("inbox");
    const [sortMode, setSortMode] = useState<SortMode>("default");
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [detailTaskId, setDetailTaskId] = useState<number | null>(null);
    const [draftTitle, setDraftTitle] = useState("");
    const [draftDescription, setDraftDescription] = useState("");
    const [draftImportant, setDraftImportant] = useState(false);
    const [draftDeadline, setDraftDeadline] = useState("");
    const [draftReminder, setDraftReminder] = useState("");
    const [createOpen, setCreateOpen] = useState(false);
    const [createTitle, setCreateTitle] = useState("");
    const [createDescription, setCreateDescription] = useState("");
    const [createPriority, setCreatePriority] = useState<Task["priority"]>("normal");
    const [createDeadline, setCreateDeadline] = useState("");
    const [createStatus, setCreateStatus] = useState<"approved" | "waiting_for">("approved");

    const { approve, dismiss, complete, start, update, createManual, isAnyPending } = useTaskMutations();
    const statsQuery = useTaskStats();

    const queryFilters = FILTER_BY_TAB[activeTab];

    const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useInfiniteQuery({
        queryKey: [
            "tasks",
            activeTab,
            queryFilters.status?.join(",") ?? null,
            queryFilters.priority?.join(",") ?? null,
        ],
        initialPageParam: 0,
        queryFn: ({ pageParam }) =>
            getTasksInfinite({
                pageParam,
                pageSize: PAGE_SIZE,
                status: queryFilters.status,
                priority: queryFilters.priority,
            }),
        getNextPageParam: (lastPage) => lastPage.nextPage,
    });

    const tasks = useMemo(() => data?.pages.flatMap((page) => page.tasks ?? []) ?? [], [data]);

    const sortedTasks = useMemo(() => {
        const priorityWeight: Record<Task["priority"], number> = {
            urgent: 0, high: 1, normal: 2, low: 3,
        };
        const list = [...tasks];

        if (sortMode === "deadline") {
            return list.sort((a, b) => {
                const deadlineA = a.deadline_at ? new Date(a.deadline_at).getTime() : Infinity;
                const deadlineB = b.deadline_at ? new Date(b.deadline_at).getTime() : Infinity;
                return deadlineA - deadlineB;
            });
        }

        if (sortMode === "priority") {
            return list.sort((a, b) => priorityWeight[a.priority] - priorityWeight[b.priority]);
        }

        // default: status weight → priority → deadline
        const statusWeight: Record<Task["status"], number> = {
            pending_approval: 0, approved: 1, in_progress: 1, waiting_for: 2, completed: 3, dismissed: 4,
        };
        return list.sort((a, b) => {
            const statusDelta = statusWeight[a.status] - statusWeight[b.status];
            if (statusDelta !== 0) return statusDelta;
            const priorityDelta = priorityWeight[a.priority] - priorityWeight[b.priority];
            if (priorityDelta !== 0) return priorityDelta;
            const deadlineA = a.deadline_at ? new Date(a.deadline_at).getTime() : Infinity;
            const deadlineB = b.deadline_at ? new Date(b.deadline_at).getTime() : Infinity;
            return deadlineA - deadlineB;
        });
    }, [tasks, sortMode]);

    const pendingTaskIds = useMemo(
        () => sortedTasks.filter((t) => t.status === "pending_approval").map((t) => t.id),
        [sortedTasks]
    );
    const activeTaskIds = useMemo(
        () => sortedTasks.filter((t) => t.status === "approved" || t.status === "in_progress").map((t) => t.id),
        [sortedTasks]
    );

    useEffect(() => { setSelectedIds(new Set()); }, [activeTab]);

    const selectedTask = useMemo(() => tasks.find((t) => t.id === detailTaskId) ?? null, [tasks, detailTaskId]);

    useEffect(() => {
        if (!selectedTask) {
            setDraftTitle(""); setDraftDescription(""); setDraftImportant(false);
            setDraftDeadline(""); setDraftReminder("");
            return;
        }
        setDraftTitle(selectedTask.title ?? "");
        setDraftDescription(selectedTask.description ?? "");
        setDraftImportant(selectedTask.priority === "urgent" || selectedTask.priority === "high");
        setDraftDeadline(selectedTask.deadline_at ? toLocalInputValue(selectedTask.deadline_at) : "");
        setDraftReminder(selectedTask.scheduled_reminder_at ? toLocalInputValue(selectedTask.scheduled_reminder_at) : "");
    }, [selectedTask]);

    const toggleSelect = (taskId: number) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(taskId)) next.delete(taskId); else next.add(taskId);
            return next;
        });
    };

    const selectAllPending = () => setSelectedIds(new Set(pendingTaskIds));
    const selectAllActive = () => setSelectedIds(new Set(activeTaskIds));
    const clearSelection = () => setSelectedIds(new Set());

    const handleBatchApprove = async () => {
        await Promise.all(Array.from(selectedIds).map((id) => approve.mutateAsync(id)));
        clearSelection();
    };
    const handleBatchReject = async () => {
        await Promise.all(Array.from(selectedIds).map((id) => dismiss.mutateAsync(id)));
        clearSelection();
    };
    const handleBatchComplete = async () => {
        await Promise.all(Array.from(selectedIds).map((id) => complete.mutateAsync(id)));
        clearSelection();
    };
    const handleMarkAllActiveDone = async () => {
        if (!activeTaskIds.length) return;
        await Promise.all(activeTaskIds.map((id) => complete.mutateAsync(id)));
        clearSelection();
    };

    const stats = statsQuery.data;
    const safeCount = (value?: number) => (typeof value === "number" && !Number.isNaN(value) ? value : 0);
    const counts: Record<TaskTab, number> = {
        inbox: safeCount(stats?.pending_approval),
        active: safeCount(stats ? stats.approved + stats.in_progress : 0),
        waiting: safeCount(stats?.waiting_for ?? 0),
        done: safeCount(stats?.completed),
    };

    const handleSaveDetails = () => {
        if (!selectedTask) return;
        const payload: {
            title?: string; description?: string; priority?: "urgent" | "high" | "normal" | "low";
            deadline?: string | null; confirm_deadline?: boolean; clear_deadline?: boolean;
            scheduled_reminder_at?: string | null;
        } = {};

        if (draftTitle.trim() && draftTitle.trim() !== selectedTask.title) payload.title = draftTitle.trim();
        if ((draftDescription ?? "") !== (selectedTask.description ?? "")) payload.description = draftDescription;

        const currentImportant = selectedTask.priority === "urgent" || selectedTask.priority === "high";
        if (draftImportant !== currentImportant) {
            payload.priority = draftImportant
                ? (selectedTask.priority === "urgent" ? "urgent" : "high")
                : "normal";
        }

        const currentDeadline = selectedTask.deadline_at ? toLocalInputValue(selectedTask.deadline_at) : "";
        if (draftDeadline !== currentDeadline) {
            if (draftDeadline) { payload.deadline = new Date(draftDeadline).toISOString(); payload.confirm_deadline = true; }
            else if (selectedTask.deadline_at) { payload.clear_deadline = true; }
        }

        const currentReminder = selectedTask.scheduled_reminder_at ? toLocalInputValue(selectedTask.scheduled_reminder_at) : "";
        if (draftReminder !== currentReminder) {
            payload.scheduled_reminder_at = draftReminder ? new Date(draftReminder).toISOString() : null;
        }

        if (Object.keys(payload).length) update.mutate({ taskId: selectedTask.id, data: payload });
    };

    const handleCreateTask = async () => {
        if (!createTitle.trim()) return;
        await createManual.mutateAsync({
            title: createTitle.trim(),
            description: createDescription.trim() ? createDescription.trim() : undefined,
            priority: createPriority,
            deadline_at: createDeadline ? new Date(createDeadline).toISOString() : undefined,
            status: createStatus,
        });
        setCreateTitle(""); setCreateDescription(""); setCreatePriority("normal"); setCreateDeadline(""); setCreateStatus("approved");
        setCreateOpen(false);
    };

    return (
        <div className="space-y-6">
            {/* ── Header ── */}
            <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                        Tasks
                    </p>
                    <button
                        type="button"
                        onClick={() => setCreateOpen(true)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[13px] font-medium text-primary border border-primary/25 bg-primary/[0.04] hover:bg-primary/[0.09] active:scale-[0.98] transition-all font-inter"
                    >
                        <Plus size={13} strokeWidth={2.5} />
                        New task
                    </button>
                </div>

                {/* Status tabs */}
                <div className="flex flex-wrap gap-2">
                    {(Object.keys(TAB_LABELS) as TaskTab[]).map((tab) => {
                        const count = counts[tab];
                        const label = count > 0 ? `${TAB_LABELS[tab]} (${count})` : TAB_LABELS[tab];
                        return (
                            <button
                                key={tab}
                                type="button"
                                onClick={() => { setActiveTab(tab); setSortMode("default"); }}
                                className={`${tabBase} ${activeTab === tab ? tabClasses[tab].active : tabClasses[tab].idle}`}
                            >
                                {label}
                            </button>
                        );
                    })}
                </div>

                {/* Sort controls */}
                <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                        Sort
                    </span>
                    {(Object.keys(SORT_LABELS) as SortMode[]).map((mode) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => setSortMode(mode)}
                            className={`${sortBase} ${
                                sortMode === mode
                                    ? "border-obsidian/40 bg-obsidian/[0.06] text-obsidian"
                                    : "border-border text-muted-foreground hover:text-foreground hover:border-border/80"
                            }`}
                        >
                            {SORT_LABELS[mode]}
                        </button>
                    ))}
                </div>
            </div>

            {/* ── Batch action bar ── */}
            {selectedIds.size > 0 && (
                <div
                    className="flex flex-wrap items-center gap-2 rounded-[14px] border border-border bg-white px-4 py-3 text-xs"
                    style={{ boxShadow: CARD_SHADOW }}
                >
                    <span className="font-semibold text-obsidian font-inter">{selectedIds.size} selected</span>
                    <button
                        type="button"
                        onClick={handleBatchApprove}
                        disabled={isAnyPending}
                        className="rounded-full border border-sage/40 px-3 py-1 font-semibold text-sage hover:bg-sage/10 disabled:opacity-50 font-inter transition-colors"
                    >
                        Approve selected
                    </button>
                    <button
                        type="button"
                        onClick={handleBatchReject}
                        disabled={isAnyPending}
                        className="rounded-full border border-burgundy/40 px-3 py-1 font-semibold text-burgundy hover:bg-burgundy/10 disabled:opacity-50 font-inter transition-colors"
                    >
                        Reject selected
                    </button>
                    {activeTab === "active" && (
                        <button
                            type="button"
                            onClick={handleBatchComplete}
                            disabled={isAnyPending}
                            className="rounded-full border border-sage/40 px-3 py-1 font-semibold text-sage hover:bg-sage/10 disabled:opacity-50 font-inter transition-colors"
                        >
                            Mark selected done
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={clearSelection}
                        className="rounded-full border border-border px-3 py-1 font-semibold text-muted-foreground hover:text-foreground font-inter transition-colors"
                    >
                        Clear
                    </button>
                </div>
            )}

            {/* ── Task list ── */}
            {isLoading ? (
                <div className="py-8 text-sm text-muted-foreground font-inter">Loading tasks…</div>
            ) : sortedTasks.length ? (
                <div className="space-y-2">
                    {sortedTasks.map((task) => (
                        <TaskItem
                            key={task.id}
                            task={task}
                            selected={selectedIds.has(task.id)}
                            onSelect={toggleSelect}
                            allowSelectActive={activeTab === "active"}
                            onOpenDetails={(taskId) => setDetailTaskId(taskId)}
                            onApprove={(taskId) => approve.mutate(taskId)}
                            onDismiss={(taskId) => dismiss.mutate(taskId)}
                            onComplete={(taskId) => complete.mutate(taskId)}
                            onStart={(taskId) => start.mutate(taskId)}
                        />
                    ))}
                </div>
            ) : (
                <p className="py-12 text-sm text-muted-foreground font-inter text-center">
                    No tasks here.
                </p>
            )}

            {/* ── Footer ── */}
            <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground font-inter">
                    {sortedTasks.length} {sortedTasks.length === 1 ? "task" : "tasks"}
                </p>
                <div className="flex items-center gap-2">
                    {pendingTaskIds.length > 0 && (
                        <button type="button" onClick={selectAllPending} className={utilBtn}>
                            Select pending
                        </button>
                    )}
                    {activeTab === "active" && activeTaskIds.length > 0 && (
                        <>
                            <button type="button" onClick={selectAllActive} className={utilBtn}>
                                Select active
                            </button>
                            <button
                                type="button"
                                onClick={handleMarkAllActiveDone}
                                className="rounded-full border border-sage/40 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-sage transition hover:bg-sage/10 font-inter"
                            >
                                Mark all done
                            </button>
                        </>
                    )}
                    {hasNextPage && (
                        <button
                            type="button"
                            onClick={() => fetchNextPage()}
                            disabled={isFetchingNextPage}
                            className={`${utilBtn} disabled:opacity-50`}
                        >
                            {isFetchingNextPage ? "Loading…" : "Show more"}
                        </button>
                    )}
                </div>
            </div>

            {/* ── Detail dialog ── */}
            <Dialog open={detailTaskId !== null} onOpenChange={(open) => { if (!open) setDetailTaskId(null); }}>
                <DialogContent className="max-w-3xl">
                    <DialogHeader>
                        <DialogTitle className="font-playfair text-xl font-semibold text-foreground">
                            Task details
                        </DialogTitle>
                    </DialogHeader>
                    {selectedTask ? (
                        <div className="space-y-5">
                            <div className="space-y-1.5">
                                <Label htmlFor="task-title" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Task</Label>
                                <Input id="task-title" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} className="font-inter" />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="task-description" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Details</Label>
                                <Textarea id="task-description" value={draftDescription} onChange={(e) => setDraftDescription(e.target.value)} rows={3} className="font-inter" />
                            </div>
                            <label className="flex items-center gap-2 text-sm font-medium text-obsidian font-inter">
                                <input
                                    type="checkbox"
                                    checked={draftImportant}
                                    onChange={(e) => setDraftImportant(e.target.checked)}
                                    className="h-4 w-4 rounded border-border accent-primary"
                                />
                                Mark as important
                            </label>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <Label htmlFor="task-deadline" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Deadline</Label>
                                    <Input id="task-deadline" type="datetime-local" value={draftDeadline} onChange={(e) => setDraftDeadline(e.target.value)} className="font-inter" />
                                    {selectedTask.deadline_at && !draftDeadline && (
                                        <span className="text-xs text-muted-foreground font-inter">(clears on save)</span>
                                    )}
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="task-reminder" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Reminder</Label>
                                    <Input id="task-reminder" type="datetime-local" value={draftReminder} onChange={(e) => setDraftReminder(e.target.value)} className="font-inter" />
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2 pt-1">
                                {selectedTask.status === "pending_approval" && (
                                    <>
                                        <button
                                            type="button"
                                            onClick={() => dismiss.mutate(selectedTask.id)}
                                            className="rounded-[8px] border border-burgundy/40 px-4 py-2 text-[13px] font-semibold text-burgundy hover:bg-burgundy/10 transition-colors font-inter"
                                        >
                                            Reject
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => approve.mutate(selectedTask.id)}
                                            className="rounded-[8px] bg-copper px-4 py-2 text-[13px] font-semibold text-white hover:bg-copper/90 active:scale-[0.97] transition-all font-inter"
                                        >
                                            Approve
                                        </button>
                                    </>
                                )}
                                <button
                                    type="button"
                                    onClick={handleSaveDetails}
                                    className="rounded-[8px] border border-border px-4 py-2 text-[13px] font-semibold text-foreground hover:bg-linen active:scale-[0.97] transition-all font-inter"
                                >
                                    Save changes
                                </button>
                            </div>
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground font-inter">Task not found.</p>
                    )}
                </DialogContent>
            </Dialog>

            {/* ── Create dialog ── */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle className="font-playfair text-xl font-semibold text-foreground">
                            New task
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="create-title" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Task</Label>
                            <Input
                                id="create-title"
                                value={createTitle}
                                onChange={(e) => setCreateTitle(e.target.value)}
                                placeholder="What needs doing?"
                                className="font-inter"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="create-description" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Details</Label>
                            <Textarea
                                id="create-description"
                                value={createDescription}
                                onChange={(e) => setCreateDescription(e.target.value)}
                                rows={3}
                                placeholder="Add context or notes"
                                className="font-inter"
                            />
                        </div>
                        <div className="grid grid-cols-3 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="create-status" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Status</Label>
                                <select
                                    id="create-status"
                                    value={createStatus}
                                    onChange={(e) => setCreateStatus(e.target.value as "approved" | "waiting_for")}
                                    className="h-9 w-full rounded-[8px] border border-border bg-white px-3 text-sm text-obsidian font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                                >
                                    <option value="approved">Active</option>
                                    <option value="waiting_for">Waiting</option>
                                </select>
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="create-priority" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Priority</Label>
                                <select
                                    id="create-priority"
                                    value={createPriority}
                                    onChange={(e) => setCreatePriority(e.target.value as Task["priority"])}
                                    className="h-9 w-full rounded-[8px] border border-border bg-white px-3 text-sm text-obsidian font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                                >
                                    <option value="urgent">Urgent</option>
                                    <option value="high">High</option>
                                    <option value="normal">Normal</option>
                                    <option value="low">Low</option>
                                </select>
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="create-deadline" className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">Deadline</Label>
                                <Input id="create-deadline" type="datetime-local" value={createDeadline} onChange={(e) => setCreateDeadline(e.target.value)} className="font-inter" />
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2 pt-1">
                            <button
                                type="button"
                                onClick={() => setCreateOpen(false)}
                                className="rounded-[8px] border border-border px-4 py-2 text-[13px] font-semibold text-muted-foreground hover:text-foreground hover:bg-linen transition-all font-inter"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleCreateTask}
                                disabled={!createTitle.trim()}
                                className="rounded-[8px] bg-primary px-4 py-2 text-[13px] font-semibold text-white hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                            >
                                Create task
                            </button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};
