"use client";

import { Message } from "@/services/messages";
import { DonnaCard, DonnaCardContent, DonnaCardHeader, DonnaCardTitle } from "@/components/ui/DonnaCard";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { formatDistanceToNow, parseISO } from "date-fns";
import { Archive, CheckCircle, Trash2, Sparkles } from "lucide-react";
import { useMessageMutations } from "@/hooks/useInbox";
import { cn } from "@/lib/utils";
import { TaskItem } from "./TaskItem";

interface EmailCardProps {
    message: Message;
    highlight?: boolean;
}

export function EmailCard({ message, highlight }: EmailCardProps) {
    const { markDone, archive, remove } = useMessageMutations();

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

    // Determine card style based on priority
    const isUrgent = message.needs_reply;
    const isInsight = message.scheduling_intent?.detected;
    const hasTasks = message.tasks && message.tasks.length > 0;

    return (
        <DonnaCard
            variant="interactive"
            className={cn(
                "group relative overflow-hidden transition-all duration-300",
                isUrgent && "border-l-4 border-l-auburn bg-linen/50", // Urgent highlight
                isInsight && "border-l-4 border-l-copper bg-white", // Insight highlight
                highlight && "ring-2 ring-auburn/40"
            )}
        >
            <DonnaCardHeader className="pb-2 flex flex-row items-start justify-between space-y-0">
                <div className="flex flex-col gap-1">
                    {/* Sender & Time */}
                    <div className="flex items-center gap-2">
                        <DonnaText variant="label" className="text-auburn font-bold">
                            {message.sender.split('<')[0].trim()}
                        </DonnaText>
                        <div className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                        <DonnaText variant="caption" className="text-muted-foreground/60 flex items-center gap-1">
                            {formatDistanceToNow(parseISO(message.received_at), { addSuffix: true })}
                        </DonnaText>
                    </div>

                    {/* Subject */}
                    <DonnaCardTitle className="text-lg font-playfair leading-tight mt-1 group-hover:text-auburn transition-colors">
                        {message.subject}
                    </DonnaCardTitle>
                </div>

                {/* Priority Indicator / Icon */}
                <div className="flex items-center gap-2">
                    {isUrgent && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-auburn/10 text-auburn text-[10px] font-bold uppercase tracking-wider">
                            Action
                        </span>
                    )}
                    {isInsight && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-copper/10 text-copper text-[10px] font-bold uppercase tracking-wider">
                            <Sparkles size={10} />
                            Insight
                        </span>
                    )}
                </div>
            </DonnaCardHeader>

            <DonnaCardContent>
                {/* Summary or Snippet */}
                <DonnaText variant="body" className="text-sm text-muted-foreground/90 line-clamp-2 leading-relaxed">
                    {message.summary || message.snippet}
                </DonnaText>

                {/* Tasks Section */}
                {hasTasks && (
                    <div className="mt-4 space-y-2">
                        <div className="h-px w-full bg-border/60 mb-3" /> {/* Separator */}
                        <DonnaText variant="label" className="text-xs text-muted-foreground uppercase tracking-widest pl-1">
                            Suggested Actions
                        </DonnaText>
                        <div className="flex flex-col gap-2">
                            {message.tasks!.map(task => (
                                <div key={task.id} onClick={(e) => e.stopPropagation()}>
                                    <TaskItem task={task} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Actions (Visible on Hover or Focus) */}
                <div className="flex items-center justify-end gap-2 mt-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <DonnaButton variant="ghost" size="icon" onClick={handleDone} className="h-8 w-8 hover:bg-sage/10 hover:text-sage" title="Mark Done">
                        <CheckCircle size={16} />
                    </DonnaButton>
                    <DonnaButton variant="ghost" size="icon" onClick={handleArchive} className="h-8 w-8 hover:bg-copper/10 hover:text-copper" title="Archive">
                        <Archive size={16} />
                    </DonnaButton>
                    <DonnaButton variant="ghost" size="icon" onClick={handleDelete} className="h-8 w-8 hover:bg-destructive/10 hover:text-destructive" title="Delete">
                        <Trash2 size={16} />
                    </DonnaButton>
                </div>
            </DonnaCardContent>
        </DonnaCard>
    );
}
