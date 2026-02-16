"use client";

import { DonnaText } from "@/components/ui/DonnaText";
import type { Task } from "@/services/messages";
import { Check, Sparkles, Clock } from "lucide-react";

interface TaskItemProps {
    task: Task;
    onApprove?: (taskId: number) => void;
    onComplete?: (taskId: number) => void;
    onStart?: (taskId: number) => void;
    onDismiss?: (taskId: number) => void;
}

const PRIORITY_COLORS: Record<string, string> = {
    urgent: "text-burgundy bg-burgundy/10",
    high: "text-auburn bg-auburn/10",
    normal: "text-teal bg-teal/10",
    low: "text-faint bg-faint/10",
};

export function TaskItem({ task, onApprove, onComplete, onStart, onDismiss }: TaskItemProps) {
    const isCompleted = task.status === "completed";
    const isDismissed = task.status === "dismissed";
    const isPending = task.status === "pending_approval";
    const isWaiting = task.status === "waiting_for";
    const isActive = task.status === "approved" || task.status === "in_progress";

    const handleClick = () => {
        if (isPending && onApprove) onApprove(task.id);
        else if (isWaiting && onStart) onStart(task.id);
        else if (isActive && onComplete) onComplete(task.id);
    };

    return (
        <button
            onClick={handleClick}
            disabled={isCompleted || isDismissed}
            aria-label={`${task.title}${isPending ? " — tap to approve" : isActive ? " — tap to complete" : isWaiting ? " — tap to start" : ""}`}
            className={`w-full text-left flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-200 border focus-visible:ring-2 focus-visible:ring-auburn/40 focus-visible:ring-offset-1 ${
                isCompleted || isDismissed
                    ? "opacity-50 border-border/40 bg-linen/50"
                    : isPending
                    ? "border-dashed border-copper/50 bg-copper/[0.03] hover:bg-copper/[0.06]"
                    : isWaiting
                    ? "border-teal/30 bg-teal/[0.03] hover:bg-teal/[0.06]"
                    : "border-border/60 bg-white/80 hover:bg-white"
            }`}
        >
            {/* Waiting bar */}
            {isWaiting && (
                <div className="w-1 self-stretch -ml-3 -my-2.5 rounded-l-lg bg-teal" />
            )}

            {/* Checkbox */}
            <div
                className={`shrink-0 w-5 h-5 rounded-md border-[1.5px] flex items-center justify-center ${
                    isCompleted
                        ? "bg-sage border-sage"
                        : isPending
                        ? "border-copper border-dashed"
                        : "border-faint/50"
                }`}
            >
                {isCompleted && <Check size={12} className="text-white" />}
                {isPending && <Sparkles size={10} className="text-copper" />}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                {isPending && (
                    <DonnaText as="span" className="text-[9px] font-bold tracking-wider text-copper uppercase block">
                        SUGGESTED BY AI
                    </DonnaText>
                )}
                {isWaiting && (
                    <DonnaText as="span" className="text-[9px] font-bold tracking-wider text-teal uppercase block">
                        WAITING FOR RESPONSE
                    </DonnaText>
                )}
                <DonnaText
                    as="span"
                    variant="caption"
                    weight="medium"
                    className={`text-sm ${isCompleted ? "line-through text-faint" : "text-obsidian"}`}
                >
                    {task.title}
                </DonnaText>
            </div>

            {/* Priority badge */}
            {task.priority !== "normal" && task.priority !== "low" && (
                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded shrink-0 ${PRIORITY_COLORS[task.priority]}`}>
                    {task.priority}
                </span>
            )}

            {/* Deadline */}
            {task.deadline_at && !isCompleted && !isDismissed && (
                <div className="flex items-center gap-1 text-faint shrink-0">
                    <Clock size={10} />
                    <span className="text-[10px] font-medium">
                        {new Date(task.deadline_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </span>
                </div>
            )}
        </button>
    );
}
