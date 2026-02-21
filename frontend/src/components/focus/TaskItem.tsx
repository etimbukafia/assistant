"use client";

import type { Task } from "@/services/messages";
import type { MouseEvent } from "react";
import { Check, Clock, X } from "lucide-react";

// Card shadow per ui_visual_design_guide.md §2 — resting card level
const CARD_SHADOW = '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)';

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
            className={`w-full text-left flex items-center gap-3 rounded-[8px] px-3 py-2.5 transition-all duration-150 border ${
                isClickable
                    // focus ring uses --primary (Peony), not auburn — design_system.md §1
                    ? "cursor-pointer focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-1 hover:-translate-y-px"
                    : "cursor-default"
            } ${
                isCompleted || isDismissed
                    ? "opacity-50 border-border/40 bg-linen/60"
                    : isPending
                    ? "border-dashed border-copper/60 bg-white"
                    : isWaiting
                    ? "border-teal/40 bg-white"
                    : "border-border/60 bg-white"
            }`}
            style={!isCompleted && !isDismissed ? { boxShadow: CARD_SHADOW } : undefined}
        >
            {isSelectable && (
                <button
                    type="button"
                    onClick={(event) => {
                        stop(event);
                        onSelect?.(task.id);
                    }}
                    className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                        selected ? "bg-obsidian border-obsidian" : "border-border/60 hover:border-obsidian/50"
                    }`}
                    aria-label={selected ? "Deselect task" : "Select task"}
                >
                    {selected && <Check size={10} className="text-white" />}
                </button>
            )}

            {/* Status circle */}
            <div
                className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center ${
                    isCompleted
                        ? "bg-sage border-sage"
                        : isPending
                        ? "border-copper border-dashed"
                        : isActive
                        ? "border-sage/60"
                        : "border-faint/50"
                }`}
            >
                {isCompleted && <Check size={10} className="text-white" />}
            </div>

            <div className="flex-1 min-w-0">
                <span className={`text-sm font-inter ${
                    isCompleted ? "line-through text-faint" : "text-obsidian"
                }`}>
                    {task.title}
                </span>
            </div>

            {task.deadline_at && !isCompleted && !isDismissed && (
                <div className="flex items-center gap-1 text-faint shrink-0">
                    <Clock size={10} />
                    <span className="text-[10px] font-medium font-inter">
                        {new Date(task.deadline_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </span>
                </div>
            )}

            <div className="flex items-center gap-1 shrink-0">
                {isPending && (onApprove || onDismiss) && (
                    <>
                        <button
                            type="button"
                            onClick={(event) => { stop(event); onDismiss?.(task.id); }}
                            className="text-[11px] font-semibold px-2 py-1 rounded-[6px] border border-burgundy/30 text-burgundy hover:bg-burgundy/10 transition-colors"
                            aria-label="Reject"
                        >
                            <X size={10} />
                        </button>
                        <button
                            type="button"
                            onClick={(event) => { stop(event); onApprove?.(task.id); }}
                            className="text-[11px] font-semibold px-2 py-1 rounded-[6px] bg-copper text-white hover:bg-copper/90 transition-colors"
                            aria-label="Approve"
                        >
                            <Check size={10} />
                        </button>
                    </>
                )}
                {isWaiting && onStart && (
                    <button
                        type="button"
                        onClick={(event) => { stop(event); onStart?.(task.id); }}
                        className="text-[11px] font-semibold px-2 py-1 rounded-[6px] border border-teal/30 text-teal hover:bg-teal/10 transition-colors font-inter"
                    >
                        Start
                    </button>
                )}
                {isActive && onComplete && (
                    <button
                        type="button"
                        onClick={(event) => { stop(event); onComplete?.(task.id); }}
                        className="text-[11px] font-semibold px-2 py-1 rounded-[6px] border border-sage/30 text-sage hover:bg-sage/10 transition-colors"
                        aria-label="Complete"
                    >
                        <Check size={10} />
                    </button>
                )}
            </div>
        </div>
    );
}
