"use client";

import { Message } from "@/services/messages";
import { formatDistanceToNow, parseISO } from "date-fns";
import { Archive, CheckCircle, RotateCcw, Trash2, Sparkles } from "lucide-react";
import { useMessageMutations } from "@/hooks/useInbox";
import { cn } from "@/lib/utils";

interface EmailCardProps {
    message: Message;
    highlight?: boolean;
    selected?: boolean;
    compact?: boolean;
    onClick?: (threadId: string) => void;
}

const CARD_SHADOW = '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)';

export function EmailCard({ message, highlight, selected, compact, onClick }: EmailCardProps) {
    const { markDone, archive, restore, remove } = useMessageMutations();

    const handleDone = (e: React.MouseEvent) => {
        e.stopPropagation();
        markDone.mutate(message.id);
    };

    const handleArchive = (e: React.MouseEvent) => {
        e.stopPropagation();
        archive.mutate(message.id);
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        remove.mutate(message.id);
    };

    const handleRestore = (e: React.MouseEvent) => {
        e.stopPropagation();
        restore.mutate(message.id);
    };

    const isUrgent = message.needs_reply;
    const isInsight = message.scheduling_intent?.detected;
    const hasTasks = message.tasks && message.tasks.length > 0;
    const taskCount = message.tasks?.length ?? 0;

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={() => onClick?.(message.thread_id || '')}
            onKeyDown={(e) => e.key === "Enter" && onClick?.(message.thread_id || '')}
            style={{ boxShadow: CARD_SHADOW }}
            className={cn(
                "group relative bg-white border border-border rounded-[14px] cursor-pointer transition-all duration-200",
                compact ? "px-3 py-2.5" : "px-4 py-3",
                isUrgent && "border-l-[3px] border-l-primary",
                isInsight && !isUrgent && "border-l-[3px] border-l-copper",
                highlight && "ring-2 ring-primary/30",
                selected && "ring-2 ring-primary/40 bg-primary/[0.02]",
                "hover:border-border/80",
            )}
        >
            {/* Top row: sender + time + badges */}
            <div className="flex items-start justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                    <span className={cn(
                        "font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter truncate",
                        compact ? "text-[10px]" : "text-[11px]"
                    )}>
                        {message.sender.split('<')[0].trim()}
                    </span>
                    <span className="h-1 w-1 rounded-full bg-muted-foreground/30 shrink-0" />
                    <span className="text-[11px] text-muted-foreground/50 font-inter shrink-0">
                        {formatDistanceToNow(parseISO(message.received_at), { addSuffix: true })}
                    </span>
                </div>

                {/* Badges */}
                <div className="flex items-center gap-1.5 shrink-0">
                    {isUrgent && (
                        <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 text-[10px] font-bold uppercase tracking-wider font-inter">
                            Reply
                        </span>
                    )}
                    {isInsight && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-copper/10 text-copper border border-copper/20 text-[10px] font-bold uppercase tracking-wider font-inter">
                            <Sparkles size={9} />
                            {!compact && "Insight"}
                        </span>
                    )}
                </div>
            </div>

            {/* Subject */}
            <p className={cn(
                "font-playfair font-semibold text-foreground leading-snug",
                compact ? "text-[14px] line-clamp-1" : "text-[17px]"
            )}>
                {message.subject}
            </p>

            {/* Summary / snippet */}
            {!compact && (
                <p className="text-sm text-muted-foreground/80 font-inter line-clamp-2 mt-1 leading-relaxed">
                    {message.summary || message.snippet}
                </p>
            )}
            {compact && (
                <p className="text-[12px] text-muted-foreground/70 font-inter line-clamp-1 mt-0.5">
                    {message.summary || message.snippet}
                </p>
            )}

            {/* Task count chip + action buttons row */}
            <div className="flex items-center justify-between mt-2.5">
                <div>
                    {hasTasks && (
                        <span className="text-[10px] font-medium font-inter text-foreground/50 bg-foreground/[0.05] px-1.5 py-0.5 rounded-[4px]">
                            {taskCount} {taskCount === 1 ? "task" : "tasks"}
                        </span>
                    )}
                </div>

                {!compact && (
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        {message.status === "archived" ? (
                            <button
                                onClick={handleRestore}
                                title="Restore to inbox"
                                className="p-1.5 rounded-[6px] text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
                            >
                                <RotateCcw size={14} />
                            </button>
                        ) : (
                            <>
                                <button
                                    onClick={handleDone}
                                    title="Mark Done"
                                    className="p-1.5 rounded-[6px] text-muted-foreground hover:text-sage hover:bg-sage/10 transition-colors"
                                >
                                    <CheckCircle size={14} />
                                </button>
                                <button
                                    onClick={handleArchive}
                                    title="Archive"
                                    className="p-1.5 rounded-[6px] text-muted-foreground hover:text-muted-foreground/80 hover:bg-muted/50 transition-colors"
                                >
                                    <Archive size={14} />
                                </button>
                            </>
                        )}
                        <button
                            onClick={handleDelete}
                            title="Delete"
                            className="p-1.5 rounded-[6px] text-muted-foreground hover:text-burgundy hover:bg-burgundy/10 transition-colors"
                        >
                            <Trash2 size={14} />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
