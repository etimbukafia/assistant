"use client";

import { Task } from "@/services/tasks";
import { useTaskMutations } from "@/hooks/useTasks";
import { Check, X, Loader2, Calendar } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { cn } from "@/lib/utils";

interface TaskItemProps {
    task: Task;
}

export function TaskItem({ task }: TaskItemProps) {
    const { approve, dismiss } = useTaskMutations();

    const isPending  = approve.isPending || dismiss.isPending;
    const isApproved = task.status === "approved" || task.status === "in_progress" || task.status === "completed";
    const isDismissed = task.status === "dismissed";

    const handleApprove = (e: React.MouseEvent) => {
        e.stopPropagation();
        approve.mutate(task.id);
    };

    const handleDismiss = (e: React.MouseEvent) => {
        e.stopPropagation();
        dismiss.mutate(task.id);
    };

    if (isDismissed) return null;

    return (
        <div className={cn(
            "flex items-start justify-between p-3 rounded-lg border transition-all",
            isApproved
                ? "bg-sage/10 border-sage/20"
                : "bg-background border-border"
        )}>
            <div className="space-y-1 flex-1 min-w-0 mr-4">
                <div className="flex items-center gap-2">
                    {isApproved && <Check size={14} className="text-sage shrink-0" />}
                    <p className={cn(
                        "text-sm font-medium font-inter truncate",
                        isApproved && "text-sage line-through"
                    )}>
                        {task.title}
                    </p>
                </div>

                {task.deadline_at && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                        <Calendar size={12} />
                        <span className="text-xs font-inter">
                            Due {formatDistanceToNow(parseISO(task.deadline_at), { addSuffix: true })}
                        </span>
                    </div>
                )}
            </div>

            {!isApproved && (
                <div className="flex items-center gap-2 shrink-0">
                    <button
                        type="button"
                        className="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-40"
                        onClick={handleDismiss}
                        disabled={isPending}
                        title="Dismiss"
                    >
                        {dismiss.isPending ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
                    </button>

                    <button
                        type="button"
                        className="h-8 px-3 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-medium font-inter flex items-center gap-1.5 transition-colors disabled:opacity-40"
                        onClick={handleApprove}
                        disabled={isPending}
                        title="Approve"
                    >
                        {approve.isPending ? (
                            <Loader2 size={14} className="animate-spin" />
                        ) : (
                            <>
                                <Check size={14} />
                                Approve
                            </>
                        )}
                    </button>
                </div>
            )}
        </div>
    );
}
