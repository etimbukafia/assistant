"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchThreadDetail, ThreadDetailResponse, ThreadMessageDetail } from "@/services/messages";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { TaskItem } from "./TaskItem";
import { ReplyComposer } from "./ReplyComposer";
import {
    Loader2, AlertCircle, ChevronDown, ChevronRight, X,
    Mail, Clock, Users, Calendar, Archive,
    CheckCircle2, ArrowRight, Zap
} from "lucide-react";
import { formatDistanceToNow, parseISO, format } from "date-fns";
import { cn } from "@/lib/utils";
import React, { useState } from "react";
import { useMessageMutations } from "@/hooks/useInbox";

interface ThreadDetailPanelProps {
    threadId: string | null;
    onClose: () => void;
}

export function ThreadDetailPanel({ threadId, onClose }: ThreadDetailPanelProps) {
    const { data, isLoading, error } = useQuery({
        queryKey: ["thread-detail", threadId],
        queryFn: () => fetchThreadDetail(threadId!),
        enabled: !!threadId,
        staleTime: 60_000, // 1 min — switching threads and back is instant
    });

    return (
        <div className="h-full flex flex-col bg-background animate-in slide-in-from-right-4 duration-300">
            {/* Top bar */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-border/40 shrink-0">
                <DonnaText variant="caption" className="text-muted-foreground/60 uppercase tracking-widest text-[10px]">
                    Thread Intelligence
                </DonnaText>
                <DonnaButton variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 text-muted-foreground hover:text-foreground">
                    <X size={16} />
                </DonnaButton>
            </div>

            {isLoading ? (
                <div className="flex-1 px-6 py-5 space-y-4 animate-pulse">
                    {/* Skeleton: summary */}
                    <div className="h-4 w-3/4 rounded bg-muted-foreground/10" />
                    <div className="h-4 w-1/2 rounded bg-muted-foreground/10" />
                    {/* Skeleton: action points card */}
                    <div className="rounded-xl border border-muted-foreground/10 p-4 space-y-3">
                        <div className="h-3 w-24 rounded bg-muted-foreground/10" />
                        <div className="h-4 w-5/6 rounded bg-muted-foreground/10" />
                        <div className="h-4 w-2/3 rounded bg-muted-foreground/10" />
                    </div>
                    {/* Skeleton: action buttons */}
                    <div className="flex gap-2">
                        <div className="h-8 w-28 rounded-md bg-muted-foreground/10" />
                        <div className="h-8 w-20 rounded-md bg-muted-foreground/10" />
                        <div className="h-8 w-20 rounded-md bg-muted-foreground/10" />
                    </div>
                    {/* Skeleton: message bubble */}
                    <div className="rounded-xl border border-muted-foreground/10 p-3 space-y-2">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-muted-foreground/10" />
                            <div className="h-4 w-32 rounded bg-muted-foreground/10" />
                        </div>
                        <div className="pl-11 space-y-2">
                            <div className="h-3 w-full rounded bg-muted-foreground/8" />
                            <div className="h-3 w-5/6 rounded bg-muted-foreground/8" />
                            <div className="h-3 w-2/3 rounded bg-muted-foreground/8" />
                        </div>
                    </div>
                </div>
            ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 text-destructive">
                    <AlertCircle size={24} />
                    <DonnaText variant="body" className="text-sm">Failed to load thread.</DonnaText>
                </div>
            ) : data ? (
                <ThreadContent data={data} threadId={threadId!} onClose={onClose} />
            ) : null}
        </div>
    );
}

function ThreadContent({ data, threadId, onClose }: { data: ThreadDetailResponse; threadId: string; onClose: () => void }) {
    const { thread_state, messages, tasks, scheduling_suggestions } = data;
    const latestMessage = messages[messages.length - 1];
    const olderMessages = messages.slice(0, -1);
    const { markDone, archive } = useMessageMutations();

    return (
        <ScrollArea className="flex-1">
            <div className="px-6 py-5 space-y-0">

                {/* ━━━ THE LOGAN ROY SECTION ━━━ */}
                <ActionPointsHero
                    actionPoints={thread_state.action_points}
                    needsReply={thread_state.needs_reply}
                    summary={thread_state.summary}
                />

                {/* Quick Actions — right after action points, above the fold */}
                <div className="flex items-center gap-2 py-4">
                    <ReplyComposer
                        messageId={latestMessage?.id}
                        originalSender={latestMessage?.sender || ""}
                        originalSubject={latestMessage?.subject || ""}
                        threadId={threadId}
                    />

                    <DonnaButton
                        variant="outline"
                        size="sm"
                        className="gap-2 border-sage/40 hover:bg-sage/10 hover:text-sage hover:border-sage"
                        onClick={() => {
                            if (latestMessage) markDone.mutate(latestMessage.id);
                            onClose();
                        }}
                    >
                        <CheckCircle2 size={14} />
                        Done
                    </DonnaButton>

                    <DonnaButton
                        variant="outline"
                        size="sm"
                        className="gap-2 border-border/40 hover:bg-copper/10 hover:text-copper hover:border-copper"
                        onClick={() => {
                            if (latestMessage) archive.mutate(latestMessage.id);
                            onClose();
                        }}
                    >
                        <Archive size={14} />
                        Archive
                    </DonnaButton>
                </div>

                <Separator className="my-1" />

                {/* ━━━ CONVERSATION ━━━ */}
                <div className="py-4 space-y-3">
                    <DonnaText variant="label" className="text-[10px] text-muted-foreground/50 uppercase tracking-[0.2em] font-bold">
                        Conversation
                    </DonnaText>

                    {/* Latest message — always expanded */}
                    {latestMessage && <MessageBubble message={latestMessage} expanded isLatest />}

                    {/* Older messages — collapsible */}
                    {olderMessages.length > 0 && (
                        <OlderMessages messages={olderMessages} />
                    )}
                </div>

                {/* ━━━ TASKS & SCHEDULING ━━━ */}
                {(tasks.length > 0 || scheduling_suggestions.length > 0) && (
                    <>
                        <Separator className="my-1" />
                        <div className="py-4 space-y-3">
                            {tasks.length > 0 && (
                                <div className="space-y-2">
                                    <DonnaText variant="label" className="text-[10px] text-muted-foreground/50 uppercase tracking-[0.2em] font-bold">
                                        Tasks
                                    </DonnaText>
                                    <div className="flex flex-col gap-2">
                                        {tasks.map(task => (
                                            <div key={task.id} onClick={(e) => e.stopPropagation()}>
                                                <TaskItem task={task} />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {scheduling_suggestions.length > 0 && (
                                <div className="space-y-2">
                                    <DonnaText variant="label" className="text-[10px] text-muted-foreground/50 uppercase tracking-[0.2em] font-bold">
                                        Scheduling
                                    </DonnaText>
                                    {scheduling_suggestions.map(suggestion => (
                                        <div key={suggestion.id} className="p-3 rounded-xl border bg-copper/5 border-copper/20 space-y-2">
                                            <div className="flex items-center gap-2">
                                                <Calendar size={14} className="text-copper" />
                                                <DonnaText variant="body" className="text-sm font-medium">
                                                    {suggestion.meeting_type} &middot; {suggestion.duration_minutes} min
                                                </DonnaText>
                                            </div>
                                            {suggestion.suggested_slots.length > 0 && (
                                                <div className="pl-6 space-y-1">
                                                    {suggestion.suggested_slots.slice(0, 3).map((slot, i) => (
                                                        <DonnaText key={i} variant="caption" className="text-muted-foreground">
                                                            {format(parseISO(slot.start_time), "EEE, MMM d 'at' h:mm a")}
                                                            {slot.has_conflict && <span className="text-destructive ml-1">(conflict)</span>}
                                                        </DonnaText>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* ━━━ METADATA FOOTER ━━━ */}
                <div className="flex items-center gap-4 text-muted-foreground/40 text-[11px] pt-4 pb-8">
                    <div className="flex items-center gap-1">
                        <Mail size={11} />
                        <span>Gmail</span>
                    </div>
                    {latestMessage && (
                        <div className="flex items-center gap-1">
                            <Clock size={11} />
                            <span>{format(parseISO(latestMessage.received_at), "MMM d, yyyy 'at' h:mm a")}</span>
                        </div>
                    )}
                    <div className="flex items-center gap-1">
                        <Users size={11} />
                        <span>{thread_state.message_count} {thread_state.message_count === 1 ? "msg" : "msgs"}</span>
                    </div>
                </div>
            </div>
        </ScrollArea>
    );
}

// ─── THE LOGAN ROY SECTION ───────────────────────────────────────────────────
// Action points dominate. Big type. Amber accent. Visible in 2 seconds.

function ActionPointsHero({
    actionPoints,
    needsReply,
    summary,
}: {
    actionPoints: string[];
    needsReply: boolean;
    summary?: string;
}) {
    const hasActionPoints = actionPoints.length > 0;

    return (
        <div className="space-y-4">
            {/* Subject-level context */}
            {summary && (
                <DonnaText variant="body" className="text-muted-foreground text-sm leading-relaxed">
                    {summary}
                </DonnaText>
            )}

            {/* Needs Reply — prominent banner */}
            {needsReply && (
                <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-auburn/8 border border-auburn/20">
                    <Zap size={16} className="text-auburn fill-auburn/20" />
                    <DonnaText variant="body" className="text-auburn font-semibold text-sm">
                        Reply needed
                    </DonnaText>
                </div>
            )}

            {/* Action Points — THE HERO */}
            {hasActionPoints && (
                <div className="rounded-xl bg-gradient-to-br from-auburn/6 via-linen/80 to-copper/4 border border-auburn/15 p-4 space-y-3">
                    <div className="flex items-center gap-2">
                        <div className="w-5 h-5 rounded-full bg-auburn/15 flex items-center justify-center">
                            <ArrowRight size={11} className="text-auburn" />
                        </div>
                        <DonnaText variant="label" className="text-[10px] text-auburn/80 uppercase tracking-[0.2em] font-bold">
                            What matters
                        </DonnaText>
                    </div>
                    <ul className="space-y-2.5">
                        {actionPoints.map((point, i) => (
                            <li key={i} className="flex items-start gap-3">
                                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-auburn shrink-0" />
                                <span className="text-[15px] font-medium leading-snug text-foreground/90">
                                    {point}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Fallback if no action points */}
            {!hasActionPoints && !needsReply && (
                <div className="text-muted-foreground/60 text-sm italic">
                    No action items detected.
                </div>
            )}
        </div>
    );
}

// ─── MESSAGE BUBBLE ──────────────────────────────────────────────────────────

function MessageBubble({
    message,
    expanded,
    onToggle,
    isLatest,
}: {
    message: ThreadMessageDetail;
    expanded: boolean;
    onToggle?: () => void;
    isLatest?: boolean;
}) {
    const senderName = message.sender.split('<')[0].trim().replace(/"/g, '');
    const initials = senderName.split(' ').filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase();

    const colors = ["bg-auburn", "bg-copper", "bg-sage", "bg-slate-500", "bg-violet-500", "bg-teal-500"];
    const colorIndex = message.sender.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % colors.length;

    return (
        <div className={cn(
            "rounded-xl border transition-all",
            expanded ? "bg-background border-border/60" : "bg-muted/20 cursor-pointer hover:bg-muted/40 border-transparent",
            isLatest && expanded && "border-auburn/15 shadow-sm"
        )}>
            <div
                className={cn("flex items-center gap-3 p-3", onToggle && "cursor-pointer")}
                onClick={onToggle}
                role={onToggle ? "button" : undefined}
            >
                <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-white text-[11px] font-bold shrink-0",
                    colors[colorIndex]
                )}>
                    {initials}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold truncate">{senderName}</span>
                        <span className="text-[11px] text-muted-foreground/50 shrink-0">
                            {formatDistanceToNow(parseISO(message.received_at), { addSuffix: true })}
                        </span>
                    </div>
                    {!expanded && (
                        <p className="text-xs text-muted-foreground/70 line-clamp-1 mt-0.5">
                            {message.summary || message.body.slice(0, 120)}
                        </p>
                    )}
                </div>

                {onToggle && (
                    expanded
                        ? <ChevronDown size={14} className="text-muted-foreground/40 shrink-0" />
                        : <ChevronRight size={14} className="text-muted-foreground/40 shrink-0" />
                )}
            </div>

            {expanded && (
                <div className="px-3 pb-4 pt-0">
                    <div className="pl-11">
                        <FormattedEmailBody body={message.body} />
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── OLDER MESSAGES ACCORDION ────────────────────────────────────────────────

function OlderMessages({ messages }: { messages: ThreadMessageDetail[] }) {
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
    const [showAll, setShowAll] = useState(false);

    const toggleExpand = (id: number) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const visibleMessages = showAll ? messages : messages.slice(-2);
    const hiddenCount = messages.length - visibleMessages.length;

    return (
        <div className="space-y-2">
            {hiddenCount > 0 && (
                <button
                    onClick={() => setShowAll(true)}
                    className="w-full text-center py-2 text-xs text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                >
                    Show {hiddenCount} earlier {hiddenCount === 1 ? "message" : "messages"}
                </button>
            )}
            {visibleMessages.map(msg => (
                <MessageBubble
                    key={msg.id}
                    message={msg}
                    expanded={expandedIds.has(msg.id)}
                    onToggle={() => toggleExpand(msg.id)}
                />
            ))}
        </div>
    );
}

// ─── FORMATTED EMAIL BODY ────────────────────────────────────────────────────
// Clean up raw email text: collapse excessive whitespace, format quoted blocks

function FormattedEmailBody({ body }: { body: string }) {
    // Split into paragraphs, clean up
    const lines = body.split('\n');
    const elements: React.ReactElement[] = [];
    let inQuote = false;
    let quoteLines: string[] = [];
    let paragraphBuffer: string[] = [];

    const flushParagraph = () => {
        if (paragraphBuffer.length > 0) {
            const text = paragraphBuffer.join(' ').trim();
            if (text) {
                elements.push(
                    <p key={`p-${elements.length}`} className="text-sm text-foreground/85 leading-relaxed mb-2.5">
                        {text}
                    </p>
                );
            }
            paragraphBuffer = [];
        }
    };

    const flushQuote = () => {
        if (quoteLines.length > 0) {
            elements.push(
                <blockquote key={`q-${elements.length}`} className="border-l-2 border-muted-foreground/20 pl-3 py-1 mb-2.5 text-xs text-muted-foreground/60 leading-relaxed">
                    {quoteLines.join('\n')}
                </blockquote>
            );
            quoteLines = [];
        }
    };

    for (const line of lines) {
        const trimmed = line.trim();

        // Detect quoted lines (> prefix or "On ... wrote:" pattern)
        if (trimmed.startsWith('>') || trimmed.match(/^On .+ wrote:$/)) {
            flushParagraph();
            if (!inQuote) inQuote = true;
            quoteLines.push(trimmed.replace(/^>\s?/, ''));
            continue;
        }

        if (inQuote) {
            flushQuote();
            inQuote = false;
        }

        // Empty line = paragraph break
        if (!trimmed) {
            flushParagraph();
            continue;
        }

        // Signature detection — stop rendering after common sig markers
        if (trimmed === '--' || trimmed.match(/^(Best|Regards|Thanks|Cheers|Sent from|Get Outlook),?\s*$/i)) {
            flushParagraph();
            elements.push(
                <p key={`sig-${elements.length}`} className="text-xs text-muted-foreground/40 leading-relaxed mt-3 border-t border-border/30 pt-2">
                    {lines.slice(lines.indexOf(line)).filter(l => l.trim()).join('\n')}
                </p>
            );
            break;
        }

        paragraphBuffer.push(trimmed);
    }

    flushParagraph();
    flushQuote();

    if (elements.length === 0) {
        return <p className="text-sm text-muted-foreground/60 italic">No content</p>;
    }

    return <div>{elements}</div>;
}

