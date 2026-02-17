"use client";

import { useEffect, useMemo, useState } from "react";
import { isToday, parseISO } from "date-fns";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getTasksInfinite } from "@/services/tasks";
import { TaskItem } from "@/components/focus/TaskItem";
import { useTaskMutations, useTaskStats, useTasks } from "@/hooks/useTasks";
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

const PAGE_SIZE = 5;

type TaskTab = "important" | "suggested" | "active" | "waiting" | "done" | "today" | "deadline";

type TagKey = "important" | "suggested" | "pending" | "done";

type QueryFilters = {
    status?: string[];
    priority?: string[];
};

const TAB_LABELS: Record<TaskTab, string> = {
    important: "Important",
    suggested: "Suggested",
    active: "Active",
    waiting: "Waiting",
    done: "Done",
    today: "Today",
    deadline: "Deadline",
};

const TAG_LABELS: Record<TagKey, string> = {
    important: "Important",
    suggested: "Suggested",
    pending: "Pending",
    done: "Done",
};

const TAGS_BY_TAB: Record<TaskTab, TagKey[]> = {
    important: ["done", "suggested", "pending"],
    suggested: ["important"],
    active: ["important"],
    waiting: ["important", "pending", "suggested"],
    done: ["important"],
    today: ["important", "suggested", "pending", "done"],
    deadline: ["important", "suggested", "pending", "done"],
};

const STATUS_BY_TAG: Record<TagKey, string[] | undefined> = {
    important: undefined,
    suggested: ["pending_approval"],
    pending: ["waiting_for"],
    done: ["completed"],
};

const PRIORITY_BY_TAG: Record<TagKey, string[] | undefined> = {
    important: ["urgent", "high"],
    suggested: undefined,
    pending: undefined,
    done: undefined,
};

const FILTER_BY_TAB: Record<TaskTab, QueryFilters> = {
    important: { priority: ["urgent", "high"] },
    suggested: { status: ["pending_approval"] },
    active: { status: ["approved", "in_progress"] },
    waiting: { status: ["waiting_for"] },
    done: { status: ["completed"] },
    today: {
        status: ["pending_approval", "approved", "in_progress", "waiting_for"],
    },
    deadline: {
        status: ["pending_approval", "approved", "in_progress", "waiting_for"],
    },
};

const intersect = (values?: string[], other?: string[]) => {
    if (!values && !other) return undefined;
    if (!values) return other ? [...other] : undefined;
    if (!other) return [...values];
    const set = new Set(other);
    const result = values.filter((value) => set.has(value));
    return result.length ? result : undefined;
};

const buildFilters = (tab: TaskTab, tag: TagKey | null): QueryFilters => {
    const base = FILTER_BY_TAB[tab];
    if (!tag) return base;

    return {
        status: intersect(base.status, STATUS_BY_TAG[tag]),
        priority: intersect(base.priority, PRIORITY_BY_TAG[tag]),
    };
};

const filterTag = (task: Task, activeTag: TagKey | null) => {
    if (!activeTag) return true;
    if (activeTag === "important") return task.priority === "urgent" || task.priority === "high";
    if (activeTag === "suggested") return task.status === "pending_approval";
    if (activeTag === "pending") return task.status === "waiting_for";
    if (activeTag === "done") return task.status === "completed";
    return true;
};

const getFilterLabel = (tab: TaskTab, count?: number) => {
    const label = TAB_LABELS[tab];
    if (typeof count === "number") return `${label} (${count})`;
    return label;
};

const toLocalInputValue = (iso: string) => {
    const date = new Date(iso);
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
        date.getDate()
    )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const ActiveTasksList = () => {
    const [activeTab, setActiveTab] = useState<TaskTab>("important");
    const [activeTag, setActiveTag] = useState<TagKey | null>("pending");
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
    const { approve, dismiss, complete, start, update, createManual, isAnyPending } = useTaskMutations();
    const statsQuery = useTaskStats();
    const importantQuery = useTasks({
        priorities: "urgent,high",
        limit: 1,
        offset: 0,
        sort: "priority",
    });

    const queryFilters = useMemo(() => buildFilters(activeTab, activeTag), [activeTab, activeTag]);

    const {
        data,
        isLoading,
        isFetchingNextPage,
        fetchNextPage,
        hasNextPage,
    } = useInfiniteQuery({
        queryKey: [
            "tasks",
            activeTab,
            activeTag,
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

    const tasks = useMemo(
        () => data?.pages.flatMap((page) => page.tasks ?? []) ?? [],
        [data]
    );

    const filteredTasks = useMemo(() => {
        if (!tasks.length) return [];
        let next = tasks.filter((task) => filterTag(task, activeTag));
        if (activeTab === "today") {
            next = next.filter((task) => {
                if (task.created_at) return isToday(parseISO(task.created_at));
                return false;
            });
        }
        if (activeTab === "deadline") {
            next = next.filter((task) => Boolean(task.deadline_at));
        }
        return next;
    }, [tasks, activeTag, activeTab]);

    const sortedTasks = useMemo(() => {
        const statusWeight: Record<Task["status"], number> = {
            pending_approval: 0,
            approved: 1,
            in_progress: 1,
            waiting_for: 2,
            completed: 3,
            dismissed: 4,
        };
        const priorityWeight: Record<Task["priority"], number> = {
            urgent: 0,
            high: 1,
            normal: 2,
            low: 3,
        };
        const list = [...filteredTasks];
        if (activeTab === "deadline") {
            return list.sort((a, b) => {
                const deadlineA = a.deadline_at ? new Date(a.deadline_at).getTime() : Infinity;
                const deadlineB = b.deadline_at ? new Date(b.deadline_at).getTime() : Infinity;
                return deadlineA - deadlineB;
            });
        }
        return list.sort((a, b) => {
            const statusDelta = statusWeight[a.status] - statusWeight[b.status];
            if (statusDelta !== 0) return statusDelta;
            const priorityDelta = priorityWeight[a.priority] - priorityWeight[b.priority];
            if (priorityDelta !== 0) return priorityDelta;
            const deadlineA = a.deadline_at ? new Date(a.deadline_at).getTime() : Infinity;
            const deadlineB = b.deadline_at ? new Date(b.deadline_at).getTime() : Infinity;
            return deadlineA - deadlineB;
        });
    }, [filteredTasks]);

    const visibleTags = TAGS_BY_TAB[activeTab];
    const pendingTaskIds = useMemo(
        () => sortedTasks.filter((task) => task.status === "pending_approval").map((task) => task.id),
        [sortedTasks]
    );
    const activeTaskIds = useMemo(
        () => sortedTasks.filter((task) => task.status === "approved" || task.status === "in_progress").map((task) => task.id),
        [sortedTasks]
    );

    useEffect(() => {
        setSelectedIds(new Set());
    }, [activeTab, activeTag]);

    const selectedTask = useMemo(
        () => tasks.find((task) => task.id === detailTaskId) ?? null,
        [tasks, detailTaskId]
    );

    useEffect(() => {
        if (!selectedTask) {
            setDraftTitle("");
            setDraftDescription("");
            setDraftImportant(false);
            setDraftDeadline("");
            setDraftReminder("");
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
            if (next.has(taskId)) {
                next.delete(taskId);
            } else {
                next.add(taskId);
            }
            return next;
        });
    };

    const selectAllPending = () => setSelectedIds(new Set(pendingTaskIds));
    const selectAllActive = () => setSelectedIds(new Set(activeTaskIds));

    const clearSelection = () => {
        setSelectedIds(new Set());
    };

    const handleBatchApprove = async () => {
        const ids = Array.from(selectedIds);
        await Promise.all(ids.map((taskId) => approve.mutateAsync(taskId)));
        clearSelection();
    };

    const handleBatchReject = async () => {
        const ids = Array.from(selectedIds);
        await Promise.all(ids.map((taskId) => dismiss.mutateAsync(taskId)));
        clearSelection();
    };

    const handleBatchComplete = async () => {
        const ids = Array.from(selectedIds);
        await Promise.all(ids.map((taskId) => complete.mutateAsync(taskId)));
        clearSelection();
    };

    const handleMarkAllActiveDone = async () => {
        if (!activeTaskIds.length) return;
        await Promise.all(activeTaskIds.map((taskId) => complete.mutateAsync(taskId)));
        clearSelection();
    };

    const stats = statsQuery.data;
    const safeCount = (value?: number) => (typeof value === "number" && !Number.isNaN(value) ? value : 0);
    const counts = {
        important: safeCount(importantQuery.data?.total),
        suggested: safeCount(stats?.pending_approval),
        active: safeCount(stats ? stats.approved + stats.in_progress : 0),
        waiting: safeCount(stats?.waiting_for ?? 0),
        done: safeCount(stats?.completed),
        today: activeTab === "today" ? safeCount(filteredTasks.length) : 0,
        deadline: activeTab === "deadline" ? safeCount(filteredTasks.length) : 0,
    };
    const resolvedCounts = (tab: TaskTab) => {
        if (tab === activeTab) return safeCount(sortedTasks.length);
        return counts[tab];
    };

    const tabBase = "rounded-full border px-4 py-1 text-sm font-medium transition";
    const tagBase = "rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition";
    const tabClasses: Record<TaskTab, { active: string; idle: string }> = {
        important: {
            active: "border-burgundy bg-burgundy text-white",
            idle: "border-burgundy/40 text-burgundy hover:text-burgundy/90",
        },
        suggested: {
            active: "border-copper bg-copper text-white",
            idle: "border-copper/40 text-copper hover:text-copper/90",
        },
        active: {
            active: "border-sage bg-sage text-white",
            idle: "border-sage/40 text-sage hover:text-sage/90",
        },
        waiting: {
            active: "border-teal bg-teal text-white",
            idle: "border-teal/40 text-teal hover:text-teal/90",
        },
        done: {
            active: "border-obsidian bg-obsidian text-white",
            idle: "border-obsidian/40 text-obsidian hover:text-obsidian/90",
        },
        today: {
            active: "border-auburn bg-auburn text-white",
            idle: "border-auburn/40 text-auburn hover:text-auburn/90",
        },
        deadline: {
            active: "border-indigo-600 bg-indigo-600 text-white",
            idle: "border-indigo-600/40 text-indigo-600 hover:text-indigo-600/90",
        },
    };
    const tagClasses: Record<TagKey, { active: string; idle: string }> = {
        important: {
            active: "border-burgundy bg-burgundy text-white",
            idle: "border-burgundy/40 text-burgundy hover:text-burgundy/90",
        },
        suggested: {
            active: "border-copper bg-copper text-white",
            idle: "border-copper/40 text-copper hover:text-copper/90",
        },
        pending: {
            active: "border-teal bg-teal text-white",
            idle: "border-teal/40 text-teal hover:text-teal/90",
        },
        done: {
            active: "border-obsidian bg-obsidian text-white",
            idle: "border-obsidian/40 text-obsidian hover:text-obsidian/90",
        },
    };

    const handleSaveDetails = () => {
        if (!selectedTask) return;
        const payload: {
            title?: string;
            description?: string;
            priority?: "urgent" | "high" | "normal" | "low";
            deadline?: string | null;
            confirm_deadline?: boolean;
            clear_deadline?: boolean;
            scheduled_reminder_at?: string | null;
        } = {};

        if (draftTitle.trim() && draftTitle.trim() !== selectedTask.title) {
            payload.title = draftTitle.trim();
        }

        if ((draftDescription ?? "") !== (selectedTask.description ?? "")) {
            payload.description = draftDescription;
        }

        const currentImportant = selectedTask.priority === "urgent" || selectedTask.priority === "high";
        if (draftImportant !== currentImportant) {
            if (draftImportant) {
                payload.priority = selectedTask.priority === "urgent" ? "urgent" : "high";
            } else {
                payload.priority = "normal";
            }
        }

        const currentDeadline = selectedTask.deadline_at
            ? toLocalInputValue(selectedTask.deadline_at)
            : "";
        if (draftDeadline !== currentDeadline) {
            if (draftDeadline) {
                payload.deadline = new Date(draftDeadline).toISOString();
                payload.confirm_deadline = true;
            } else if (selectedTask.deadline_at) {
                payload.clear_deadline = true;
            }
        }

        const currentReminder = selectedTask.scheduled_reminder_at
            ? toLocalInputValue(selectedTask.scheduled_reminder_at)
            : "";
        if (draftReminder !== currentReminder) {
            payload.scheduled_reminder_at = draftReminder ? new Date(draftReminder).toISOString() : null;
        }

        if (Object.keys(payload).length) {
            update.mutate({ taskId: selectedTask.id, data: payload });
        }
    };

    const handleCreateTask = async () => {
        if (!createTitle.trim()) return;
        await createManual.mutateAsync({
            title: createTitle.trim(),
            description: createDescription.trim() ? createDescription.trim() : undefined,
            priority: createPriority,
            deadline_at: createDeadline ? new Date(createDeadline).toISOString() : undefined,
        });
        setCreateTitle("");
        setCreateDescription("");
        setCreatePriority("normal");
        setCreateDeadline("");
        setCreateOpen(false);
    };

    return (
        <div className="space-y-6">
            <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <p className="text-[12px] font-semibold tracking-[0.24em] text-muted-foreground">
                        TASKS
                    </p>
                    <button
                        type="button"
                        onClick={() => setCreateOpen(true)}
                        className="rounded-full border border-border px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition hover:text-foreground"
                    >
                        New task
                    </button>
                </div>
                <div className="flex flex-wrap gap-2">
                    {(Object.keys(TAB_LABELS) as TaskTab[]).map((tab) => (
                        <button
                            key={tab}
                            type="button"
                            onClick={() => {
                                setActiveTab(tab);
                                setActiveTag(tab === "important" ? "pending" : null);
                            }}
                            className={`${tabBase} ${
                                activeTab === tab ? tabClasses[tab].active : tabClasses[tab].idle
                            }`}
                        >
                            {getFilterLabel(tab, resolvedCounts(tab))}
                        </button>
                    ))}
                </div>
                <div className="flex flex-wrap gap-2">
                    {visibleTags.map((tag) => {
                        const isActive = activeTag === tag;
                        return (
                            <button
                                key={tag}
                                type="button"
                                onClick={() => setActiveTag(isActive ? null : tag)}
                                className={`${tagBase} ${
                                    isActive ? tagClasses[tag].active : tagClasses[tag].idle
                                }`}
                            >
                                {TAG_LABELS[tag]}
                            </button>
                        );
                    })}
                </div>
            </div>

            {selectedIds.size > 0 && (
                <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-border/60 bg-white/80 px-4 py-3 text-xs">
                    <span className="font-semibold text-obsidian">
                        {selectedIds.size} selected
                    </span>
                    <button
                        type="button"
                        onClick={handleBatchApprove}
                        disabled={isAnyPending}
                        className="rounded-full border border-sage/40 px-3 py-1 font-semibold text-sage hover:bg-sage/10 disabled:opacity-50"
                    >
                        Approve selected
                    </button>
                    <button
                        type="button"
                        onClick={handleBatchReject}
                        disabled={isAnyPending}
                        className="rounded-full border border-burgundy/40 px-3 py-1 font-semibold text-burgundy hover:bg-burgundy/10 disabled:opacity-50"
                    >
                        Reject selected
                    </button>
                    {activeTab === "active" && (
                        <button
                            type="button"
                            onClick={handleBatchComplete}
                            disabled={isAnyPending}
                            className="rounded-full border border-sage/40 px-3 py-1 font-semibold text-sage hover:bg-sage/10 disabled:opacity-50"
                        >
                            Mark selected done
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={clearSelection}
                        className="rounded-full border border-border px-3 py-1 font-semibold text-muted-foreground hover:text-foreground"
                    >
                        Clear
                    </button>
                </div>
            )}

            {isLoading ? (
                <div className="py-8 text-sm text-muted-foreground">Loading tasks...</div>
            ) : sortedTasks.length ? (
                <div className="space-y-3">
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
                <div className="rounded-2xl border border-dashed border-border px-6 py-8 text-sm text-muted-foreground">
                    No tasks match this view.
                </div>
            )}

            <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                    Showing {sortedTasks.length} {sortedTasks.length === 1 ? "task" : "tasks"}
                </div>
                <div className="flex items-center gap-2">
                    {pendingTaskIds.length > 0 && (
                        <button
                            type="button"
                            onClick={selectAllPending}
                            className="rounded-full border border-border px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition hover:text-foreground"
                        >
                            Select pending
                        </button>
                    )}
                    {activeTab === "active" && activeTaskIds.length > 0 && (
                        <>
                            <button
                                type="button"
                                onClick={selectAllActive}
                                className="rounded-full border border-border px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition hover:text-foreground"
                            >
                                Select active
                            </button>
                            <button
                                type="button"
                                onClick={handleMarkAllActiveDone}
                                className="rounded-full border border-sage/40 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-sage transition hover:bg-sage/10"
                            >
                                Mark all done
                            </button>
                        </>
                    )}
                    {hasNextPage ? (
                        <button
                            type="button"
                            onClick={() => fetchNextPage()}
                            disabled={isFetchingNextPage}
                            className="rounded-full border border-border px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition hover:text-foreground disabled:opacity-50"
                        >
                            {isFetchingNextPage ? "Loading..." : "Show more"}
                        </button>
                    ) : null}
                </div>
            </div>

            <Dialog
                open={detailTaskId !== null}
                onOpenChange={(open) => {
                    if (!open) setDetailTaskId(null);
                }}
            >
                <DialogContent className="max-w-3xl">
                    <DialogHeader>
                        <DialogTitle>Task details</DialogTitle>
                    </DialogHeader>
                    {selectedTask ? (
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <Label htmlFor="task-title">Task</Label>
                                <Input
                                    id="task-title"
                                    value={draftTitle}
                                    onChange={(event) => setDraftTitle(event.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="task-description">Details</Label>
                                <Textarea
                                    id="task-description"
                                    value={draftDescription}
                                    onChange={(event) => setDraftDescription(event.target.value)}
                                    rows={3}
                                />
                            </div>
                            <div className="flex flex-wrap items-center gap-6">
                                <label className="flex items-center gap-2 text-sm font-medium text-obsidian">
                                    <input
                                        type="checkbox"
                                        checked={draftImportant}
                                        onChange={(event) => setDraftImportant(event.target.checked)}
                                        className="h-4 w-4 rounded border-border"
                                    />
                                    Mark as important
                                </label>
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="task-deadline" className="text-xs uppercase tracking-wide text-muted-foreground">
                                        Deadline
                                    </Label>
                                    <Input
                                        id="task-deadline"
                                        type="datetime-local"
                                        value={draftDeadline}
                                        onChange={(event) => setDraftDeadline(event.target.value)}
                                    />
                                    {selectedTask.deadline_at && !draftDeadline && (
                                        <span className="text-xs text-muted-foreground">(clears on save)</span>
                                    )}
                                </div>
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="task-reminder" className="text-xs uppercase tracking-wide text-muted-foreground">
                                        Reminder
                                    </Label>
                                    <Input
                                        id="task-reminder"
                                        type="datetime-local"
                                        value={draftReminder}
                                        onChange={(event) => setDraftReminder(event.target.value)}
                                    />
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {selectedTask.status === "pending_approval" && (
                                    <>
                                        <button
                                            type="button"
                                            onClick={() => dismiss.mutate(selectedTask.id)}
                                            className="rounded-full border border-burgundy/40 px-4 py-2 text-sm font-semibold text-burgundy hover:bg-burgundy/10"
                                        >
                                            Reject
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => approve.mutate(selectedTask.id)}
                                            className="rounded-full bg-copper px-4 py-2 text-sm font-semibold text-white hover:bg-copper/90"
                                        >
                                            Approve
                                        </button>
                                    </>
                                )}
                                <button
                                    type="button"
                                    onClick={handleSaveDetails}
                                    className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-obsidian hover:bg-obsidian/5"
                                >
                                    Save changes
                                </button>
                            </div>

                        </div>
                    ) : (
                        <div className="text-sm text-muted-foreground">Task not found.</div>
                    )}
                </DialogContent>
            </Dialog>

            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle>New task</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="create-title">Task</Label>
                            <Input
                                id="create-title"
                                value={createTitle}
                                onChange={(event) => setCreateTitle(event.target.value)}
                                placeholder="Enter task title"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="create-description">Details</Label>
                            <Textarea
                                id="create-description"
                                value={createDescription}
                                onChange={(event) => setCreateDescription(event.target.value)}
                                rows={3}
                                placeholder="Add context or notes"
                            />
                        </div>
                        <div className="flex flex-wrap items-center gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="create-priority" className="text-xs uppercase tracking-wide text-muted-foreground">
                                    Priority
                                </Label>
                                <select
                                    id="create-priority"
                                    value={createPriority}
                                    onChange={(event) => setCreatePriority(event.target.value as Task["priority"])}
                                    className="h-9 rounded-md border border-border bg-white px-3 text-sm text-obsidian"
                                >
                                    <option value="urgent">Urgent</option>
                                    <option value="high">High</option>
                                    <option value="normal">Normal</option>
                                    <option value="low">Low</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="create-deadline" className="text-xs uppercase tracking-wide text-muted-foreground">
                                    Deadline
                                </Label>
                                <Input
                                    id="create-deadline"
                                    type="datetime-local"
                                    value={createDeadline}
                                    onChange={(event) => setCreateDeadline(event.target.value)}
                                />
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <button
                                type="button"
                                onClick={() => setCreateOpen(false)}
                                className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleCreateTask}
                                className="rounded-full bg-obsidian px-4 py-2 text-sm font-semibold text-white hover:bg-obsidian/90"
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
