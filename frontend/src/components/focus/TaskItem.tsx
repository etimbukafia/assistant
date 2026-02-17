"use client";

import { DonnaText } from "@/components/ui/DonnaText";
import type { Task } from "@/services/messages";
import type { MouseEvent } from "react";
import { Check, Clock, X } from "lucide-react";

export type TaskTag = "important" | "suggested" | "pending" | "done";

interface TaskItemProps {
    task: Task;
    selected?: boolean;
    onSelect?: (taskId: number) => void;
    allowSelectActive?: boolean;
    onOpenDetails?: (taskId: number) => void;
    onApprove?: (taskId: number) => void;
    onComplete?: (taskId: number) => void;
    onStart?: (taskId: number) => void;
    onDismiss?: (taskId: number) => void;
}

export function TaskItem({
    task,
    selected,
    onSelect,
    allowSelectActive,
    onOpenDetails,
    onApprove,
    onComplete,
    onStart,
    onDismiss,
}: TaskItemProps) {
    const isCompleted = task.status === "completed";
    const isDismissed = task.status === "dismissed";
    const isPending = task.status === "pending_approval";
    const isWaiting = task.status === "waiting_for";
    const isActive = task.status === "approved" || task.status === "in_progress";
    const isSelectable = Boolean(onSelect) && (isPending || (allowSelectActive && isActive));

    const isClickable = Boolean(onOpenDetails);
    const handleOpen = () => {
        if (onOpenDetails) onOpenDetails(task.id);
    };

    const stop = (event: MouseEvent) => event.stopPropagation();

    return (
        <div
            role={isClickable ? "button" : undefined}
            tabIndex={isClickable ? 0 : -1}
            onClick={isClickable ? handleOpen : undefined}
            onKeyDown={
                isClickable
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") handleOpen();
                    }
                    : undefined
            }
            className={`w-full text-left flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-150 border ${
                isClickable ? "cursor-pointer focus-visible:ring-2 focus-visible:ring-auburn/40 focus-visible:ring-offset-1" : "cursor-default"
            } ${
                isCompleted || isDismissed
                    ? "opacity-50 border-border/40 bg-linen/60"
                    : isPending
                    ? "border-dashed border-copper/60 bg-white"
                    : isWaiting
                    ? "border-teal/40 bg-white"
                    : "border-border/60 bg-white"
            }`}
        >
            {isSelectable && (
                <button
                    type="button"
                    onClick={(event) => {
                        stop(event);
                        onSelect(task.id);
                    }}
                    className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center ${
                        selected ? "bg-obsidian border-obsidian" : "border-border/60"
                    }`}
                    aria-label={selected ? "Deselect task" : "Select task"}
                >
                    {selected && <Check size={10} className="text-white" />}
                </button>
            )}

            <div
                className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center ${
                    isCompleted
                        ? "bg-sage border-sage"
                        : isPending
                        ? "border-copper border-dashed"
                        : "border-faint/50"
                }`}
            >
                {isCompleted && <Check size={10} className="text-white" />}
            </div>

            <div className="flex-1 min-w-0">
                <DonnaText
                    as="span"
                    variant="caption"
                    weight="medium"
                    className={`text-sm ${isCompleted ? "line-through text-faint" : "text-obsidian"}`}
                >
                    {task.title}
                </DonnaText>
            </div>

            {task.deadline_at && !isCompleted && !isDismissed && (
                <div className="flex items-center gap-1 text-faint shrink-0">
                    <Clock size={10} />
                    <span className="text-[10px] font-medium">
                        {new Date(task.deadline_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </span>
                </div>
            )}

            <div className="flex items-center gap-1 shrink-0">
                {isPending && (onApprove || onDismiss) && (
                    <>
                        <button
                            type="button"
                            onClick={(event) => {
                                stop(event);
                                onDismiss?.(task.id);
                            }}
                            className="text-[11px] font-semibold px-2 py-1 rounded-full border border-burgundy/30 text-burgundy hover:bg-burgundy/10"
                            aria-label="Reject"
                        >
                            <X size={10} />
                        </button>
                        <button
                            type="button"
                            onClick={(event) => {
                                stop(event);
                                onApprove?.(task.id);
                            }}
                            className="text-[11px] font-semibold px-2 py-1 rounded-full bg-copper text-white hover:bg-copper/90"
                            aria-label="Approve"
                        >
                            <Check size={10} />
                        </button>
                    </>
                )}
                {isWaiting && onStart && (
                    <button
                        type="button"
                        onClick={(event) => {
                            stop(event);
                            onStart?.(task.id);
                        }}
                        className="text-[11px] font-semibold px-2 py-1 rounded-full border border-teal/30 text-teal hover:bg-teal/10"
                    >
                        Start
                    </button>
                )}
                {isActive && onComplete && (
                    <button
                        type="button"
                        onClick={(event) => {
                            stop(event);
                            onComplete?.(task.id);
                        }}
                        className="text-[11px] font-semibold px-2 py-1 rounded-full border border-sage/30 text-sage hover:bg-sage/10"
                        aria-label="Complete"
                    >
                        <Check size={10} />
                    </button>
                )}
            </div>
        </div>
    );
}
