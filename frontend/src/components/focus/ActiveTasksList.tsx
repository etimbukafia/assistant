"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getTasksInfinite } from "@/services/tasks";
import { TaskItem } from "@/components/focus/TaskItem";
import { useTaskMutations } from "@/hooks/useTasks";
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

type TaskTab = "important" | "suggested" | "active" | "waiting" | "done" | "all";

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
  all: "All",
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
  all: ["important", "suggested", "pending", "done"],
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
  all: {
    status: ["pending_approval", "approved", "in_progress", "waiting_for", "completed"],
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

const isEncryptedBody = (body?: string) => {
  if (!body) return false;
  if (body.startsWith("gAAAA")) return true;
  const base64Like = /^[A-Za-z0-9+/=]+$/.test(body);
  return base64Like && body.length > 120;
};

export const ActiveTasksList = () => {
  const [activeTab, setActiveTab] = useState<TaskTab>("important");
  const [activeTag, setActiveTag] = useState<TagKey | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [detailTaskId, setDetailTaskId] = useState<number | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftImportant, setDraftImportant] = useState(false);
  const [draftDeadline, setDraftDeadline] = useState("");
  const [draftReminder, setDraftReminder] = useState("");
  const { approve, dismiss, complete, start, update, isAnyPending } = useTaskMutations();

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
    return tasks.filter((task) => filterTag(task, activeTag));
  }, [tasks, activeTag]);

  const visibleTags = TAGS_BY_TAB[activeTab];
  const pendingTaskIds = useMemo(
    () => filteredTasks.filter((task) => task.status === "pending_approval").map((task) => task.id),
    [filteredTasks]
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

  const selectAllPending = () => {
    setSelectedIds(new Set(pendingTaskIds));
  };

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

  return (
    <section className="space-y-6">
      <header className="space-y-3">
        <p className="text-[12px] font-semibold tracking-[0.24em] text-muted-foreground">
          TASKS
        </p>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(TAB_LABELS) as TaskTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => {
                setActiveTab(tab);
                setActiveTag(null);
              }}
              className={`rounded-full border px-4 py-1 text-sm font-medium transition ${
                activeTab === tab
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {getFilterLabel(tab)}
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
                className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition ${
                  isActive
                    ? "border-foreground bg-foreground text-background"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {TAG_LABELS[tag]}
              </button>
            );
          })}
        </div>
      </header>

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
      ) : filteredTasks.length ? (
        <div className="space-y-3">
          {filteredTasks.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              selected={selectedIds.has(task.id)}
              onSelect={toggleSelect}
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
          Showing {filteredTasks.length} {filteredTasks.length === 1 ? "task" : "tasks"}
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

      <div className="text-xs text-muted-foreground">
        Need to review a task email? Check the inbox for the source message.
        {" "}
        <Link href="/dashboard/inbox" className="text-foreground underline">
          Go to inbox
        </Link>
        .
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

              <div className="rounded-2xl border border-border/60 bg-linen/60 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Source email</div>
                  <Link
                    href={`/dashboard/inbox?messageId=${selectedTask.message_id}`}
                    className="text-xs font-semibold text-obsidian underline"
                  >
                    Open in Inbox
                  </Link>
                </div>
                <div className="text-sm font-semibold text-obsidian">
                  {selectedTask.source_message?.subject ?? "Message details unavailable"}
                </div>
                <div className="text-xs text-muted-foreground">
                  {selectedTask.source_message?.sender ?? "Unknown sender"} •{" "}
                  {selectedTask.source_message?.received_at
                    ? new Date(selectedTask.source_message.received_at).toLocaleString("en-US")
                    : "Date unavailable"}
                </div>
                {selectedTask.source_message?.summary && (
                  <p className="text-sm text-obsidian">{selectedTask.source_message.summary}</p>
                )}
                {!isEncryptedBody(selectedTask.source_message?.body) &&
                  selectedTask.source_message?.body && (
                    <p className="text-xs text-muted-foreground line-clamp-4">
                      {selectedTask.source_message.body}
                    </p>
                  )}
                {isEncryptedBody(selectedTask.source_message?.body) && (
                  <p className="text-xs text-muted-foreground">
                    Email content is protected. Open in inbox to view.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Task not found.</div>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
};
